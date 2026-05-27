"""
WhatsApp Webhook — Conversational AI Bot

Flow:
  1. User sends message → extract entities silently
  2. Ask ONLY missing fields
  3. Generate images → user picks
  4. Show caption → proceed or edit
  5. Select platforms
  6. Check connections → connect missing ones
  7. Post Now or Schedule

Draft auto-saved at every step.
User can always resume from exact last step.
"""
import asyncio
import traceback
import httpx
import re
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.core.config import settings
from app.integrations.whatsapp.whatsapp_client import send_message, send_buttons, send_image, send_list
from app.services.draft_service import draft_service
from app.services.intent_service import detect_intent, BOT_CAPABILITIES, get_off_topic_response
from app.services.entity_extraction_service import (
    extract_entities, get_missing_fields, build_missing_fields_message
)
from app.services.user_service import user_service
from app.services.post_service import post_service
from app.services.scheduler_service import scheduler_service
from app.integrations.image_provider import generate_images
from app.integrations.groq.groq_client import generate_caption

router = APIRouter(tags=["WhatsApp Webhook"])
webhook_lock = asyncio.Lock()

ALL_PLATFORMS = ["instagram", "linkedin", "threads", "twitter"]
MAX_IMAGES = 5

# ── Discard keywords ──────────────────────────────────────────
DISCARD_KEYWORDS = [
    "cancel", "discard", "delete draft", "start over",
    "stop", "stop this", "abort", "reset", "new post"
]


# ──────────────────────────────────────────────────────────────
# VERIFY
# ──────────────────────────────────────────────────────────────

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN):
        return int(params.get("hub.challenge"))
    return {"error": "Verification failed"}


# ──────────────────────────────────────────────────────────────
# RECEIVE MESSAGE
# ──────────────────────────────────────────────────────────────

@router.post("/webhook")
async def receive_message(
    payload: dict,
    db: Session = Depends(get_db),
):
    async with webhook_lock:
        try:
            entry = payload.get("entry", [])
            if not entry:
                return {"success": True}
            value = entry[0].get("changes", [{}])[0].get("value", {})
            if "messages" not in value:
                return {"success": True}

            message = value["messages"][0]
            contacts = value.get("contacts", [])
            if not contacts:
                return {"success": True}

            phone = contacts[0].get("wa_id")
            msg_type = message.get("type")
            msg_id = message.get("id", "")

            # ── Deduplication — skip already-processed messages ──
            import redis as redis_lib
            from app.core.config import settings as _settings
            try:
                _redis = redis_lib.from_url(_settings.REDIS_URL)
                dedup_key = f"wa_msg:{msg_id}"
                if _redis.get(dedup_key):
                    print(f"DUPLICATE MESSAGE SKIPPED: {msg_id}")
                    return {"success": True}
                _redis.setex(dedup_key, 300, "1")  # expire after 5 min
            except Exception as _e:
                print(f"DEDUP REDIS ERROR: {_e}")

            print(f"\n{'='*40}\nFROM: {phone} | TYPE: {msg_type}\n{'='*40}")

            user = user_service.get_or_create(db, phone)

            if msg_type == "image":
                return await _handle_user_image(phone, message, user, db)
            if msg_type == "video":
                return await _handle_user_video(phone, message, user, db)
            if msg_type == "interactive":
                # Handle both button_reply and list_reply
                interactive = message.get("interactive", {})
                if interactive.get("type") == "list_reply":
                    # Treat list reply same as button reply
                    list_id = interactive.get("list_reply", {}).get("id", "")
                    message["interactive"]["button_reply"] = {"id": list_id, "title": ""}
                return await _handle_button(phone, message, user, db)
            if msg_type == "text":
                text = message["text"].get("body", "").strip()
                return await _handle_text(phone, text, user, db)

            return {"success": True}

        except Exception as e:
            print("WEBHOOK ERROR:", e)
            traceback.print_exc()
            return {"success": False}


# ──────────────────────────────────────────────────────────────
# TEXT HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_text(phone: str, text: str, user, db: Session) -> dict:
    text_lower = text.lower().strip()

    # ── Check active draft ────────────────────────────
    active_draft = draft_service.get_active_draft(db, str(user.id))

    # ── Hard-coded fast commands (no AI needed) ───────
    if text_lower in ("retry", "try again", "post again") and active_draft:
        if active_draft.current_step == "ready_to_post":
            await send_message(phone, "🔄 Retrying your post...")
            return await _check_connections_and_proceed(phone, active_draft, user, db)

    if text_lower in ("help", "/help"):
        await send_message(phone, BOT_CAPABILITIES)
        return {"success": True}


    if any(kw in text_lower for kw in DISCARD_KEYWORDS) and active_draft:
        return await _show_discard_confirmation(phone, active_draft, db)

    # ── Steps that expect raw text input — bypass intent detection ──
    TEXT_INPUT_STEPS = ("schedule_input", "caption_edit", "collecting_missing")
    if active_draft and active_draft.current_step in TEXT_INPUT_STEPS:
        return await _handle_draft_step(phone, text, active_draft, user, db)

    # ── Always run intent detection first ────────────────
    intent_data = await detect_intent(text)
    intent = intent_data.get("intent", "unknown")
    print(f"INTENT: {intent} | confidence={intent_data.get('confidence', 0)}")

    # ── Handle off-topic and questions immediately ────────
    if intent == "off_topic":
        await send_message(phone, get_off_topic_response())
        return {"success": True}

    if intent == "question":
        answer = intent_data.get("answer") or BOT_CAPABILITIES
        await send_message(phone, answer)
        return {"success": True}

    if intent == "greeting":
        if active_draft:
            return await _show_resume_prompt(phone, active_draft, db)
        await send_message(phone, "Hi! Send me a topic to create a post. Type *help* to see all features.")
        return {"success": True}

    if intent == "generate_image":
        subject = intent_data.get("image_subject") or text
        return await _handle_generate_image_request(phone, subject, user, db)

    if intent == "post_history":
        return await _handle_post_history(phone, user, db)

    if intent == "cancel_schedule":
        return await _handle_cancel_schedule(phone, user, db)

    if intent == "retry" and active_draft:
        await send_message(phone, "🔄 Retrying your post...")
        return await _check_connections_and_proceed(phone, active_draft, user, db)

    if intent == "resume" and active_draft:
        return await _show_resume_prompt(phone, active_draft, db)

    if intent == "discard" and active_draft:
        return await _show_discard_confirmation(phone, active_draft, db)

    if active_draft and active_draft.current_step not in ("done", "publishing", "ready_to_post"):
        if intent in ("create_post", "unknown"):
            return await _handle_draft_step(phone, text, active_draft, user, db)

    if intent in ("create_post", "unknown"):
        if active_draft and active_draft.current_step == "ready_to_post":
            return await _show_resume_prompt(phone, active_draft, db)
        return await _start_new_post(phone, text, user, db)

    return await _start_new_post(phone, text, user, db)
import asyncio
import traceback
import httpx
import re
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.core.config import settings
from app.integrations.whatsapp.whatsapp_client import send_message, send_buttons, send_image, send_list
from app.services.draft_service import draft_service
from app.services.intent_service import detect_intent, BOT_CAPABILITIES, get_off_topic_response
from app.services.entity_extraction_service import (
    extract_entities, get_missing_fields, build_missing_fields_message
)
from app.services.user_service import user_service
from app.services.post_service import post_service
from app.services.scheduler_service import scheduler_service
from app.integrations.image_provider import generate_images
from app.integrations.groq.groq_client import generate_caption

router = APIRouter(tags=["WhatsApp Webhook"])
webhook_lock = asyncio.Lock()

ALL_PLATFORMS = ["instagram", "linkedin", "threads", "twitter"]
MAX_IMAGES = 5

# ── Discard keywords ──────────────────────────────────────────
DISCARD_KEYWORDS = [
    "cancel", "discard", "delete draft", "start over",
    "stop", "stop this", "abort", "reset", "new post"
]


# ──────────────────────────────────────────────────────────────
# VERIFY
# ──────────────────────────────────────────────────────────────

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if (params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN):
        return int(params.get("hub.challenge"))
    return {"error": "Verification failed"}


# ──────────────────────────────────────────────────────────────
# RECEIVE MESSAGE
# ──────────────────────────────────────────────────────────────

@router.post("/webhook")
async def receive_message(
    payload: dict,
    db: Session = Depends(get_db),
):
    async with webhook_lock:
        try:
            entry = payload.get("entry", [])
            if not entry:
                return {"success": True}
            value = entry[0].get("changes", [{}])[0].get("value", {})
            if "messages" not in value:
                return {"success": True}

            message = value["messages"][0]
            contacts = value.get("contacts", [])
            if not contacts:
                return {"success": True}

            phone = contacts[0].get("wa_id")
            msg_type = message.get("type")
            msg_id = message.get("id", "")

            # ── Deduplication — skip already-processed messages ──
            import redis as redis_lib
            from app.core.config import settings as _settings
            try:
                _redis = redis_lib.from_url(_settings.REDIS_URL)
                dedup_key = f"wa_msg:{msg_id}"
                if _redis.get(dedup_key):
                    print(f"DUPLICATE MESSAGE SKIPPED: {msg_id}")
                    return {"success": True}
                _redis.setex(dedup_key, 300, "1")  # expire after 5 min
            except Exception as _e:
                print(f"DEDUP REDIS ERROR: {_e}")

            print(f"\n{'='*40}\nFROM: {phone} | TYPE: {msg_type}\n{'='*40}")

            user = user_service.get_or_create(db, phone)

            if msg_type == "image":
                return await _handle_user_image(phone, message, user, db)
            if msg_type == "video":
                return await _handle_user_video(phone, message, user, db)
            if msg_type == "interactive":
                # Handle both button_reply and list_reply
                interactive = message.get("interactive", {})
                if interactive.get("type") == "list_reply":
                    # Treat list reply same as button reply
                    list_id = interactive.get("list_reply", {}).get("id", "")
                    message["interactive"]["button_reply"] = {"id": list_id, "title": ""}
                return await _handle_button(phone, message, user, db)
            if msg_type == "text":
                text = message["text"].get("body", "").strip()
                return await _handle_text(phone, text, user, db)

            return {"success": True}

        except Exception as e:
            print("WEBHOOK ERROR:", e)
            traceback.print_exc()
            return {"success": False}


# ──────────────────────────────────────────────────────────────
# TEXT HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_text(phone: str, text: str, user, db: Session) -> dict:
    text_lower = text.lower().strip()

    # ── Check active draft ────────────────────────────
    active_draft = draft_service.get_active_draft(db, str(user.id))

    # ── Hard-coded fast commands (no AI needed) ───────
    if text_lower in ("retry", "try again", "post again") and active_draft:
        if active_draft.current_step == "ready_to_post":
            await send_message(phone, "🔄 Retrying your post...")
            return await _check_connections_and_proceed(phone, active_draft, user, db)

    if text_lower in ("help", "/help"):
        await send_message(phone, BOT_CAPABILITIES)
        return {"success": True}


    if any(kw in text_lower for kw in DISCARD_KEYWORDS) and active_draft:
        return await _show_discard_confirmation(phone, active_draft, db)

    # ── Steps that expect raw text input — bypass intent detection ──
    TEXT_INPUT_STEPS = ("schedule_input", "caption_edit", "collecting_missing")
    if active_draft and active_draft.current_step in TEXT_INPUT_STEPS:
        return await _handle_draft_step(phone, text, active_draft, user, db)

    # ── Always run intent detection first ────────────────
    intent_data = await detect_intent(text)
    intent = intent_data.get("intent", "unknown")
    print(f"INTENT: {intent} | confidence={intent_data.get('confidence', 0)}")

    # ── Handle off-topic and questions immediately ────────
    if intent == "off_topic":
        await send_message(phone, get_off_topic_response())
        return {"success": True}

    if intent == "generate_image":
        subject = intent_data.get("subject") or text
        return await _handle_generate_image_request(phone, subject, user, db)

    if intent == "post_history":
        return await _handle_post_history(phone, user, db)

    if intent == "cancel_schedule":
        return await _handle_cancel_schedule(phone, user, db)

    if intent == "question":
        answer = intent_data.get("answer") or BOT_CAPABILITIES
        await send_message(phone, answer)
        return {"success": True}

    if intent == "greeting":
        if active_draft:
            return await _show_resume_prompt(phone, active_draft, db)
        await send_message(phone, "Hi! Send me a topic to create a post. Type *help* to see all features.")
        return {"success": True}

    if intent == "retry" and active_draft:
        await send_message(phone, "🔄 Retrying your post...")
        return await _check_connections_and_proceed(phone, active_draft, user, db)

    if intent == "resume" and active_draft:
        return await _show_resume_prompt(phone, active_draft, db)

    if intent == "discard" and active_draft:
        return await _show_discard_confirmation(phone, active_draft, db)

    # ── If in middle of draft step and intent is post-related ─
    if active_draft and active_draft.current_step not in ("done", "publishing", "ready_to_post"):
        if intent in ("create_post", "unknown"):
            return await _handle_draft_step(phone, text, active_draft, user, db)

    # ── Start new post or resume ──────────────────────────
    if intent in ("create_post", "unknown"):
        if active_draft and active_draft.current_step == "ready_to_post":
            return await _show_resume_prompt(phone, active_draft, db)
        return await _start_new_post(phone, text, user, db)

    return await _start_new_post(phone, text, user, db)


# ──────────────────────────────────────────────────────────────
# START NEW POST — entity extraction
# ──────────────────────────────────────────────────────────────

async def _start_new_post(phone: str, text: str, user, db: Session) -> dict:
    """
    New simplified flow:
    1. Extract all entities from message
    2. Default image_count=1 if not mentioned
    3. Store platforms if mentioned
    4. Generate image+caption immediately
    5. Show preview → user approves or edits
    6. Ask platform only if not extracted
    7. Check connections → post
    """
    draft = draft_service.create_draft(db, user)
    await send_message(phone, "✨ On it! Generating your post...")

    # Extract entities silently
    extracted = await extract_entities(text)
    print(f"EXTRACTED: {extracted}")

    # Smart defaults
    if not extracted.get("image_count"):
        extracted["image_count"] = 1

    # If story/reel extracted, force Instagram
    if extracted.get("post_type") in ("story", "reel"):
        if not extracted.get("platforms"):
            extracted["platforms"] = ["instagram"]
        elif "instagram" not in extracted["platforms"]:
            extracted["platforms"] = ["instagram"]

    # Save all extracted data
    if extracted:
        draft_service.update_extracted_data(db, draft, extracted)

    # Only ask if topic missing
    if not extracted.get("topic"):
        draft_service.update_step(db, draft, "collecting_missing")
        await send_message(phone, "What would you like to post about?")
        return {"success": True}

    # Always ask image count unless user explicitly mentioned a number in message
    import re as _re
    user_mentioned_count = bool(_re.search(r'\b[1-5]\b|\bone\b|\btwo\b|\bthree\b|\bfour\b|\bfive\b', text.lower()))
    if user_mentioned_count and extracted.get("image_count"):
        return await _proceed_to_image_generation(phone, draft, user, db)

    # Ask how many images via list
    topic = extracted.get("topic", "your post")
    draft_service.update_step(db, draft, "collecting_missing")
    await send_message(phone, f"Got it! How many images for *{topic}*?")
    await asyncio.sleep(0.3)
    await _send_image_count_list(phone)
    return {"success": True}



async def _handle_draft_step(
    phone: str, text: str, draft, user, db: Session
) -> dict:
    step = draft.current_step
    print(f"DRAFT STEP: {step}")

    # ── Waiting for missing fields ────────────────────
    if step == "collecting_missing":
        extracted = draft.extracted_data or {}
        missing = get_missing_fields(extracted)

        if "topic" in missing:
            # User is providing topic
            draft_service.update_extracted_data(db, draft, {"topic": text})
            missing.remove("topic")

        if "image_count" in missing:
            count = _extract_count(text)
            if count == -1:
                await send_message(phone, f"Maximum {MAX_IMAGES} images. Please choose 1-{MAX_IMAGES}.")
                await _send_image_count_buttons(phone)
                return {"success": True}
            if count:
                draft_service.set_image_count(db, draft, count)
                missing.remove("image_count") if "image_count" in missing else None

        # Check again after updates
        missing = get_missing_fields(draft.extracted_data or {})
        if missing:
            msg = build_missing_fields_message(missing)
            await send_message(phone, msg)
            if missing == ["image_count"]:
                await _send_image_count_buttons(phone)
            return {"success": True}

        # All fields collected — proceed
        return await _proceed_to_image_generation(phone, draft, user, db)

    # ── Caption editing ───────────────────────────────
    if step == "caption_edit":
        draft_service.set_edited_caption(db, draft, text)
        draft_service.update_step(db, draft, "caption_review")
        caption = text
        await send_message(phone, f"✅ Caption updated:\n\n{caption}")
        await asyncio.sleep(0.5)
        await _send_caption_actions(phone)
        return {"success": True}

    # ── Schedule time input ───────────────────────────
    if step == "schedule_input":
        scheduled_time = scheduler_service.parse_schedule_time(text)
        if not scheduled_time:
            await send_message(phone, "Couldn't understand that. Try 'tomorrow 9am' or 'after 2 hours'.")
            return {"success": False}

        draft_service.set_schedule(db, draft, scheduled_time)
        draft_service.update_step(db, draft, "ready_to_post")

        platforms = (draft.extracted_data or {}).get("platforms", [])
        platforms_str = " + ".join(p.title() for p in platforms)
        formatted = scheduled_time.strftime("%d %b %Y at %I:%M %p")

        # Create scheduled jobs
        await _execute_schedule(phone, draft, user, db, scheduled_time)
        return {"success": True}

    # ── User responding during image generation wait ──
    if step == "image_generation":
        await send_message(phone, "⏳ Still generating your images, please wait...")
        return {"success": True}

    # ── Unexpected text — show resume prompt ──────────
    return await _show_resume_prompt(phone, draft, db)


# ──────────────────────────────────────────────────────────────
# BUTTON HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_button(phone: str, message: dict, user, db: Session) -> dict:
    button_id = (
        message.get("interactive", {})
        .get("button_reply", {})
        .get("id", "")
    )
    print("BUTTON:", button_id)

    draft = draft_service.get_active_draft(db, str(user.id))

    # ── Resume/Discard confirmation buttons ──────────
    if button_id == "resume_draft":
        if draft:
            return await _resume_draft(phone, draft, user, db)
        await send_message(phone, "No active draft found. Send me a topic to start!")
        return {"success": True}

    if button_id == "discard_permanently":
        if draft:
            draft_service.mark_discarded(db, draft)
            await send_message(phone, "🗑 Draft discarded. Send me a new topic whenever you're ready!")
        return {"success": True}

    if button_id == "save_and_exit":
        await send_message(
            phone,
            "✅ Draft saved! Send *hi* or any message to resume it later."
        )
        return {"success": True}

    if button_id == "continue_editing":
        if draft:
            return await _resume_draft(phone, draft, user, db)
        return {"success": True}

    # ── Image count buttons ───────────────────────────
    if button_id.startswith("img_count_"):
        count = int(button_id.replace("img_count_", ""))
        if not draft:
            await send_message(phone, "Session expired. Please send your topic again.")
            return {"success": True}
        draft_service.set_image_count(db, draft, count)
        # Check if we now have everything
        missing = get_missing_fields(draft.extracted_data or {})
        missing = [m for m in missing if m != "image_count"]
        if missing:
            msg = build_missing_fields_message(missing)
            await send_message(phone, msg)
        else:
            await _proceed_to_image_generation(phone, draft, user, db)
        return {"success": True}

    # ── Image selection ───────────────────────────────
    if button_id.startswith("pick_img_"):
        if not draft:
            return {"success": True}
        index = int(button_id.replace("pick_img_", ""))
        images = (draft.generated_assets or {}).get("generated_images", [])
        if index < len(images):
            draft_service.set_selected_images(db, draft, [images[index]])
            draft_service.update_step(db, draft, "caption_review")
            return await _show_caption(phone, draft, db)
        return {"success": True}

    if button_id == "pick_all_imgs":
        if not draft:
            return {"success": True}
        images = (draft.generated_assets or {}).get("generated_images", [])
        draft_service.set_selected_images(db, draft, images)
        draft_service.update_step(db, draft, "caption_review")
        return await _show_caption(phone, draft, db)

    if button_id == "regenerate_imgs":
        if not draft:
            return {"success": True}
        return await _proceed_to_image_generation(phone, draft, user, db)

    # ── Caption actions ───────────────────────────────
    if button_id == "caption_proceed":
        if not draft:
            return {"success": True}
        assets = draft.generated_assets or {}
        has_video = bool(assets.get("video_url"))

        if has_video:
            # Video: skip post type selection — only one option (video post)
            # Go straight to platform selection
            draft_service.update_extracted_data(db, draft, {"post_type": "post"})
            draft_service.update_step(db, draft, "platform_selection")
            await _send_platform_selection(phone, draft)
        else:
            # Image: ask Regular Post or Story
            await _send_post_type_selection(phone, has_video=False)
            draft_service.update_step(db, draft, "post_type_selection")
        return {"success": True}

    if button_id == "quick_post":
        if not draft:
            return {"success": True}
        db.refresh(draft)
        data = draft.extracted_data or {}
        assets = draft.generated_assets or {}
        has_video = bool(assets.get("video_url"))
        post_type = data.get("post_type")

        # If post_type already extracted from message (e.g. "post as story on instagram")
        # skip asking and proceed directly
        if post_type in ("story", "reel"):
            return await _proceed_after_post_type(phone, draft, user, db)

        # Always ask post type so user can choose Regular Post, Story, or Reel
        await _send_post_type_selection(phone, has_video=has_video)
        draft_service.update_step(db, draft, "post_type_selection")
        return {"success": True}

    if button_id == "proceed_after_type":
        if not draft:
            return {"success": True}
        return await _proceed_after_post_type(phone, draft, user, db)

    if button_id == "caption_edit":
        if not draft:
            return {"success": True}
        draft_service.update_step(db, draft, "caption_edit")
        await send_message(phone, "✏️ Send your new caption:")
        return {"success": True}

    if button_id == "caption_regenerate":
        if not draft:
            return {"success": True}
        await send_message(phone, "✨ Regenerating caption...")
        topic = (draft.extracted_data or {}).get("topic", "")
        instruction = (draft.extracted_data or {}).get("caption_instruction", "")
        caption = await generate_caption(f"{topic}. {instruction}".strip(". "))
        draft_service.set_caption(db, draft, caption)
        draft_service.update_step(db, draft, "caption_review")
        await send_message(phone, f"📝 *New caption:*\n\n{caption}")
        await asyncio.sleep(0.5)
        await _send_caption_actions(phone)
        return {"success": True}

    # ── Platform combination selection (one tap = final choice) ──
    PLATFORM_COMBOS = {
        "plat_instagram":  ["instagram"],
        "plat_linkedin":   ["linkedin"],
        "plat_threads":    ["threads"],
        "plat_twitter":    ["twitter"],
        "plat_ig_li":      ["instagram", "linkedin"],
        "plat_ig_th":      ["instagram", "threads"],
        "plat_li_th":      ["linkedin", "threads"],
        "plat_ig_tw":      ["instagram", "twitter"],
        "plat_li_tw":      ["linkedin", "twitter"],
        "plat_ig_li_th":   ["instagram", "linkedin", "threads"],
        "plat_ig_li_tw":   ["instagram", "linkedin", "twitter"],
        "plat_all":        ["instagram", "linkedin", "threads", "twitter"],
        "plat_vid_all":    ["instagram", "threads", "twitter"],
        "plat_th_tw":      ["threads", "twitter"],
        "select_all_platforms": ["instagram", "linkedin", "threads", "twitter"],
    }

    if button_id in PLATFORM_COMBOS or button_id.startswith("platform_"):
        if not draft:
            return {"success": True}

        if button_id in PLATFORM_COMBOS:
            platforms = PLATFORM_COMBOS[button_id]
        else:
            # Legacy single platform toggle
            platform = button_id.replace("platform_", "")
            platforms = list((draft.extracted_data or {}).get("platforms") or [])
            if platform in platforms:
                platforms.remove(platform)
            else:
                platforms.append(platform)

        # Force platform save using psycopg2 directly to bypass SQLAlchemy JSON cache
        from sqlalchemy.orm.attributes import flag_modified
        import copy
        new_data = copy.deepcopy(dict(draft.extracted_data or {}))
        new_data["platforms"] = platforms
        draft.extracted_data = new_data
        flag_modified(draft, "extracted_data")
        db.add(draft)
        db.commit()
        db.refresh(draft)

        saved = (draft.extracted_data or {}).get("platforms", [])
        print(f"PLATFORMS SAVED IN DB: {saved}")

        platforms_str = " + ".join(p.title() for p in saved)
        await send_message(phone, f"✅ Selected: *{platforms_str}*")
        await asyncio.sleep(0.5)
        await _show_preview(phone, draft, db)
        return {"success": True}

    # ── Proceed to check connections ──────────────────
    if button_id == "proceed_to_post":
        if not draft:
            return {"success": True}
        return await _check_connections_and_proceed(phone, draft, user, db)

    # ── Post type selection ──────────────────────────────────
    # ── Cancel scheduled post ────────────────────────────
    if button_id.startswith("cancel_job_"):
        from app.models.publish_job import PublishJob
        import uuid
        key = button_id.replace("cancel_job_", "")
        # Cancel all jobs for this draft or post
        try:
            jobs = (
                db.query(PublishJob)
                .filter(
                    PublishJob.user_id == user.id,
                    PublishJob.status == "pending",
                    (PublishJob.draft_id == key) | (PublishJob.post_id == key),
                )
                .all()
            )
            for job in jobs:
                job.status = "failed"
                job.error_message = "Cancelled by user"
            db.commit()
            count = len(jobs)
            if count:
                await send_message(phone, f"✅ Cancelled {count} scheduled job(s).")
            else:
                await send_message(phone, "Could not find that scheduled post.")
        except Exception as e:
            await send_message(phone, f"Could not cancel: {str(e)[:100]}")
        return {"success": True}

    # ── Story image selection ────────────────────────────
    if button_id.startswith("story_img_"):
        if not draft:
            return {"success": True}
        index = int(button_id.replace("story_img_", ""))
        assets = draft.generated_assets or {}
        images = assets.get("selected_images", [])
        if index < len(images):
            draft_service.set_selected_images(db, draft, [images[index]])
            await send_message(
                phone,
                f"✅ Image {index + 1} selected for your story!\n\n"
                "⭕ Will be posted as an Instagram Story (visible for 24 hours).\n\n"
                "ℹ️ Only Instagram supports Stories — posting on Instagram only."
            )
            await asyncio.sleep(0.5)
            draft_service.update_step(db, draft, "ready_to_post")
            await _show_preview(phone, draft, db)
        return {"success": True}

    if button_id.startswith("post_type_"):
        if not draft:
            return {"success": True}
        post_type = button_id.replace("post_type_", "")
        draft_service.update_extracted_data(db, draft, {"post_type": post_type})

        # Reel and Story = Instagram only
        if post_type in ("reel", "story"):
            draft_service.set_platforms(db, draft, ["instagram"])
            if post_type == "reel":
                await send_message(
                    phone,
                    "🎬 *Reel selected!*\n\nYour video will be posted as an Instagram Reel.\n\nℹ️ Only Instagram supports Reels — so we will post on Instagram only."
                )
                await asyncio.sleep(0.5)
                draft_service.update_step(db, draft, "ready_to_post")
                await _show_preview(phone, draft, db)
                return {"success": True}

            else:  # story
                assets = draft.generated_assets or {}
                selected_images = assets.get("selected_images", [])
                video_url = assets.get("video_url")

                # Instagram API does NOT support video stories (officially removed)
                # Only image stories work via the API
                if video_url:
                    await send_message(
                        phone,
                        "⭕ Instagram Stories only support images. Video stories are not available via API. Your video will be posted as a Reel instead."
                    )
                    await asyncio.sleep(0.5)
                    draft_service.update_extracted_data(db, draft, {"post_type": "post"})
                    draft_service.update_step(db, draft, "ready_to_post")
                    await _show_preview(phone, draft, db)
                    return {"success": True}

                if len(selected_images) > 1:
                    # Story supports only 1 image — ask user to pick one
                    await send_message(
                        phone,
                        "⭕ *Story selected!*\n\n"
                        "ℹ️ Instagram Stories support only *1 image or video* at a time.\n\n"
                        f"You selected {len(selected_images)} images. "
                        "Please pick ONE image to use as your story:"
                    )
                    await asyncio.sleep(0.5)
                    # Show pick buttons for each image
                    buttons = [
                        {"id": f"story_img_{i}", "title": f"Use Image {i+1}"}
                        for i in range(min(len(selected_images), 3))
                    ]
                    await send_buttons(phone, "Choose one image for your story:", buttons)
                    if len(selected_images) > 3:
                        more_buttons = [
                            {"id": f"story_img_{i}", "title": f"Use Image {i+1}"}
                            for i in range(3, min(len(selected_images), 5))
                        ]
                        await asyncio.sleep(0.5)
                        await send_buttons(phone, "More:", more_buttons)
                    draft_service.update_step(db, draft, "story_image_selection")
                    return {"success": True}

                # Single image or video — proceed
                await send_message(
                    phone,
                    "⭕ *Story selected!*\n\nYour content will be posted as an Instagram Story (visible for 24 hours).\n\nℹ️ Only Instagram supports Stories — so we will post on Instagram only."
                )
                await asyncio.sleep(0.5)
                draft_service.update_step(db, draft, "ready_to_post")
                await _show_preview(phone, draft, db)
                return {"success": True}

        # Regular post or video — proceed with platform/schedule logic
        return await _proceed_after_post_type(phone, draft, user, db)

    # ── Post Now ──────────────────────────────────────
    if button_id == "post_now":
        if not draft:
            return {"success": True}
        # Always check connections before posting
        db.refresh(draft)
        platforms = (draft.extracted_data or {}).get("platforms", [])
        from app.services.social_account_service import social_account_service
        missing = social_account_service.get_missing_platforms(
            db=db, whatsapp_number=user.number, platforms=platforms
        )
        if missing:
            return await _check_connections_and_proceed(phone, draft, user, db)
        return await _execute_post_now(phone, draft, user, db)

    # ── Schedule ──────────────────────────────────────
    if button_id == "schedule_post":
        if not draft:
            return {"success": True}
        data = draft.extracted_data or {}
        if data.get("scheduled_time"):
            # Already have schedule from extraction
            await _execute_schedule(phone, draft, user, db, data["scheduled_time"])
        else:
            draft_service.update_step(db, draft, "schedule_input")
            await send_message(
                phone,
                "📅 When should I post?\n\nExamples:\n- tomorrow 9am\n- after 2 hours\n- tonight 8pm"
            )
        return {"success": True}

    # ── Retry after failure ───────────────────────────
    if button_id == "retry_post":
        if not draft:
            return {"success": True}
        draft.draft_status = "active"
        db.commit()
        return await _execute_post_now(phone, draft, user, db)

    return {"success": True}


# ──────────────────────────────────────────────────────────────
# USER SENDS OWN IMAGE
# ──────────────────────────────────────────────────────────────


async def _handle_user_video(phone: str, message: dict, user, db: Session) -> dict:
    """User sends a video directly in WhatsApp chat."""
    media_id = message.get("video", {}).get("id")
    caption_text = message.get("video", {}).get("caption", "").strip()

    if not media_id:
        await send_message(phone, "Could not read video. Please try again.")
        return {"success": False}

    existing_draft = draft_service.get_active_draft(db, str(user.id))
    await send_message(phone, "🎥 Got your video! Uploading...")

    try:
        video_url = await _download_and_upload_media(media_id, "video")
        if not video_url:
            await send_message(phone, "Could not process video. Please try again.")
            return {"success": False}

        # Use existing draft or create new
        draft = existing_draft or draft_service.create_draft(db, user)

        # If user included caption text with video, extract entities from it
        if caption_text:
            extracted = await extract_entities(caption_text)
            print(f"VIDEO CAPTION EXTRACTED: {extracted}")
            if extracted.get("platforms"):
                draft_service.update_extracted_data(db, draft, {
                    "platforms": extracted["platforms"],
                    "schedule": extracted.get("schedule"),
                    "post_type": "post",  # video post
                })
            elif extracted.get("schedule"):
                draft_service.update_extracted_data(db, draft, {
                    "schedule": extracted["schedule"],
                })

        # Save video URL and mark post_type as video
        draft_service.update_generated_assets(db, draft, {"video_url": video_url})
        draft_service.update_extracted_data(db, draft, {"post_type": "post"})

        # Generate caption using topic or video caption text
        topic = (draft.extracted_data or {}).get("topic") or caption_text or "social media video"
        instruction = (draft.extracted_data or {}).get("caption_instruction", "")
        caption = await generate_caption(f"{topic}. {instruction}".strip(". "))
        draft_service.set_caption(db, draft, caption)
        draft_service.update_step(db, draft, "caption_review")

        # Show caption
        await send_message(phone, f"📝 *Caption:*\n\n{caption}")
        await asyncio.sleep(0.5)

        # Show platform/schedule info if already extracted
        data = draft.extracted_data or {}
        platforms = data.get("platforms")
        schedule = data.get("schedule")
        if platforms or schedule:
            info = []
            if platforms:
                info.append(f"📱 Platform: {' + '.join(p.title() for p in platforms)}")
            if schedule:
                info.append(f"🕐 Schedule: {schedule}")
            await send_message(phone, "\n".join(info))
            await asyncio.sleep(0.3)

        await _send_caption_actions(phone)

    except Exception as e:
        print("USER VIDEO ERROR:", e)
        import traceback
        traceback.print_exc()
        await send_message(phone, "Something went wrong. Please try again.")

    return {"success": True}


async def _send_post_type_selection(phone: str, has_video: bool = False):
    """
    Image → Regular Post or Story (Instagram only)
    Video → Video Post or Reel (Instagram only)
    Story removed from video — not supported via API.
    LinkedIn skipped for video — chunked upload not implemented.
    """
    if has_video:
        # Video Story not supported by Instagram API
        # Only option is Video Post (posted as Reel on Instagram)
        await send_buttons(
            phone,
            "Your video is ready to post!",
            [
                {"id": "post_type_post", "title": "📹 Post Video"},
            ],
        )
    else:
        await send_buttons(
            phone,
            "How do you want to post this image?",
            [
                {"id": "post_type_post",  "title": "📸 Regular Post"},
                {"id": "post_type_story", "title": "⭕ Story (Instagram)"},
            ],
        )


async def _download_and_upload_media(media_id: str, media_type: str = "image") -> str | None:
    """
    Download media from WhatsApp and upload to Cloudinary for public URL.
    Works for both images and videos.
    Returns public Cloudinary URL or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            # Step 1: Get WhatsApp media download URL
            meta_resp = await client.get(
                f"https://graph.facebook.com/v20.0/{media_id}",
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
            wa_url = meta_resp.json().get("url")
            if not wa_url:
                print(f"MEDIA: no URL in response: {meta_resp.json()}")
                return None

            # Step 2: Download media bytes
            print(f"MEDIA: downloading {media_type} from WhatsApp...")
            media_resp = await client.get(
                wa_url,
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
            media_bytes = media_resp.content
            print(f"MEDIA: downloaded {len(media_bytes)} bytes")

        # Step 3: Upload to Cloudinary
        print(f"MEDIA: uploading to Cloudinary...")
        from app.integrations.cloudinary_client import upload_media
        public_url = upload_media(media_bytes, media_type, f"wa_{media_type}_{media_id}")
        print(f"MEDIA: public URL = {public_url}")
        return public_url

    except Exception as e:
        print(f"MEDIA UPLOAD ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def _handle_user_image(phone: str, message: dict, user, db: Session) -> dict:
    """User sends an image directly in WhatsApp chat."""
    media_id = message.get("image", {}).get("id")
    caption_text = message.get("image", {}).get("caption", "").strip()

    if not media_id:
        await send_message(phone, "Could not read image. Please try again.")
        return {"success": False}

    # If active draft at image selection step, replace the image
    existing_draft = draft_service.get_active_draft(db, str(user.id))
    step = existing_draft.current_step if existing_draft else None

    await send_message(phone, "📸 Got your image! Uploading...")

    try:
        image_url = await _download_and_upload_media(media_id, "image")
        if not image_url:
            await send_message(phone, "Could not process image. Please try again.")
            return {"success": False}

        draft = existing_draft or draft_service.create_draft(db, user)

        # Extract entities from caption if provided (e.g. "post on Instagram tomorrow")
        if caption_text:
            extracted = await extract_entities(caption_text)
            print(f"IMAGE CAPTION EXTRACTED: {extracted}")
            updates = {}
            if extracted.get("platforms"):
                updates["platforms"] = extracted["platforms"]
            if extracted.get("schedule"):
                updates["schedule"] = extracted["schedule"]
            if extracted.get("post_type"):
                updates["post_type"] = extracted["post_type"]
            if extracted.get("caption_instruction"):
                updates["caption_instruction"] = extracted["caption_instruction"]
            if updates:
                draft_service.update_extracted_data(db, draft, updates)

        # Save image
        draft_service.update_generated_assets(db, draft, {
            "user_image": True,
            "video_url": None,
        })
        draft_service.set_selected_images(db, draft, [image_url])
        draft_service.set_generated_images(db, draft, [image_url])

        # Generate caption
        topic = (draft.extracted_data or {}).get("topic") or caption_text or "social media post"
        instruction = (draft.extracted_data or {}).get("caption_instruction", "")
        caption = await generate_caption(f"{topic}. {instruction}".strip(". "))
        draft_service.set_caption(db, draft, caption)
        draft_service.update_step(db, draft, "caption_review")

        await send_image(phone, image_url, "")
        await asyncio.sleep(0.5)
        await send_message(phone, f"📝 *Caption:*\n\n{caption}")
        await asyncio.sleep(0.5)
        await _send_caption_actions(phone)

    except Exception as e:
        print("USER IMAGE ERROR:", e)
        import traceback
        traceback.print_exc()
        await send_message(phone, "Something went wrong. Please try again.")

    return {"success": True}


async def _proceed_to_image_generation(phone: str, draft, user, db: Session) -> dict:
    """
    Generate image(s) + caption, then show unified preview.
    User sees everything at once and approves or edits.
    """
    # Always refresh from DB to get latest image_count
    db.refresh(draft)
    data = draft.extracted_data or {}
    topic = data.get("topic", "social media post")
    count = int(data.get("image_count") or 1)
    print(f"GENERATING: topic={topic} count={count}")
    instruction = data.get("caption_instruction", "")
    platforms = data.get("platforms") or []
    schedule = data.get("scheduled_time") or data.get("schedule")

    draft_service.update_step(db, draft, "image_generation")

    # Inform user about image count option
    if count == 1:
        await send_message(
            phone,
            f"✨ Generating 1 image for *{topic}*...\n\n"
            "💡 Tip: You can ask for up to 5 images, e.g. 'post about AI with 3 images'"
        )
    else:
        await send_message(phone, f"✨ Generating {count} images for *{topic}*...")

    # Generate caption
    caption_prompt = f"{topic}. {instruction}".strip(". ")
    caption = await generate_caption(caption_prompt)
    draft_service.set_caption(db, draft, caption)

    # Generate images
    image_prompt = f"aesthetic social media post about: {topic}, high quality, vibrant"
    draft_service.set_image_prompt(db, draft, image_prompt)
    images = generate_images(image_prompt, count)
    draft_service.set_generated_images(db, draft, images)
    draft_service.set_selected_images(db, draft, images)  # default = all selected
    draft_service.update_step(db, draft, "caption_review")

    # Show all images first
    for i, img_url in enumerate(images):
        await send_image(phone, img_url, f"Image {i+1}" if count > 1 else "")
        await asyncio.sleep(0.5)

    # Then caption and preview
    preview_lines = [f"📝 *Caption:*\n{caption}"]
    if platforms:
        preview_lines.append(f"📱 *Platform:* {' + '.join(p.title() for p in platforms)}")
    if schedule:
        preview_lines.append(f"🕐 *Schedule:* {schedule}")

    await send_message(phone, "\n\n".join(preview_lines))
    await asyncio.sleep(0.5)

    await send_buttons(
        phone,
        "Happy with this?",
        [
            {"id": "quick_post",       "title": "🚀 Post This"},
            {"id": "caption_edit",     "title": "✏️ Edit Caption"},
            {"id": "regenerate_imgs",  "title": "🔄 New Images"},
        ],
    )
    return {"success": True}



async def _show_caption(phone: str, draft, db: Session) -> dict:
    """Show caption and ask proceed/edit/regenerate."""
    caption = draft_service.get_effective_caption(draft)
    selected = (draft.generated_assets or {}).get("selected_images", [])
    count = len(selected)

    img_note = f" ({count} images selected)" if count > 1 else ""
    await send_message(phone, f"📝 *Caption{img_note}:*\n\n{caption}")
    await asyncio.sleep(0.5)
    await _send_caption_actions(phone)
    return {"success": True}


async def _send_platform_selection(phone: str, draft) -> None:
    """
    Show platform list filtered by post type.
    - Image/carousel → all 4 platforms
    - Video post → Instagram, Threads, Twitter (LinkedIn not supported)
    - Reel → Instagram only (auto-set, no selection needed)
    - Story → Instagram only (auto-set, no selection needed)
    """
    data = draft.extracted_data or {}
    post_type = data.get("post_type", "post")
    has_video = bool((draft.generated_assets or {}).get("video_url"))

    if has_video or post_type in ("video", "reel"):
        # Video: LinkedIn not supported, Instagram = Reel, others = Video Post
        await send_list(
            phone,
            body="Select platform(s) for your video:",
            button_label="Select Platform",
            sections=[
                {
                    "title": "Single Platform",
                    "rows": [
                        {"id": "plat_instagram", "title": "Instagram (as Reel)", "description": "Best reach"},
                        {"id": "plat_threads",   "title": "Threads",             "description": "Video post"},
                        {"id": "plat_twitter",   "title": "Twitter",             "description": "Requires paid plan"},
                    ],
                },
                {
                    "title": "Multiple Platforms",
                    "rows": [
                        {"id": "plat_ig_th",   "title": "Instagram + Threads",  "description": "Recommended"},
                        {"id": "plat_ig_tw",   "title": "Instagram + Twitter",  "description": "2 platforms"},
                        {"id": "plat_th_tw",   "title": "Threads + Twitter",    "description": "2 platforms"},
                        {"id": "plat_vid_all", "title": "All Video Platforms",  "description": "Insta+Threads+Twitter"},
                    ],
                },
            ],
        )
    else:
        # Image: all 4 platforms
        await send_list(
            phone,
            body="Which platform(s) to post on?",
            button_label="Select Platform",
            sections=[
                {
                    "title": "Single Platform",
                    "rows": [
                        {"id": "plat_instagram", "title": "Instagram",  "description": "Image post"},
                        {"id": "plat_linkedin",  "title": "LinkedIn",   "description": "Image post"},
                        {"id": "plat_threads",   "title": "Threads",    "description": "Image post"},
                        {"id": "plat_twitter",   "title": "Twitter ⚠️",  "description": "Requires paid plan ($100/mo)"},
                    ],
                },
                {
                    "title": "Multiple Platforms",
                    "rows": [
                        {"id": "plat_ig_li",     "title": "Instagram + LinkedIn",      "description": "2 platforms"},
                        {"id": "plat_ig_th",     "title": "Instagram + Threads",       "description": "2 platforms"},
                        {"id": "plat_ig_li_th",  "title": "Insta+LinkedIn+Threads",   "description": "3 platforms"},
                        {"id": "plat_all",       "title": "All 4 Platforms",           "description": "Instagram, LinkedIn, Threads, Twitter"},
                    ],
                },
            ],
        )


async def _show_preview(phone: str, draft, db: Session) -> dict:
    """
    Show full preview before posting:
    - Caption
    - Number of images selected
    - Platform(s)
    - Schedule if set
    Then ask: Post Now / Schedule / Edit
    """
    data = draft.extracted_data or {}
    assets = draft.generated_assets or {}

    caption = draft_service.get_effective_caption(draft)
    platforms = data.get("platforms") or []
    selected_images = assets.get("selected_images", [])
    video_url = assets.get("video_url")
    schedule = data.get("scheduled_time") or data.get("schedule")

    # Build preview message
    lines = ["📋 *Post Preview*"]
    lines.append(f"📝 Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}")
    if video_url:
        lines.append("🎥 Video: 1")
    else:
        lines.append(f"🖼 Images: {len(selected_images)}")
    if platforms:
        lines.append(f"📱 Platforms: {' + '.join(p.title() for p in platforms)}")
    if schedule:
        lines.append(f"🕐 Schedule: {schedule}")

    preview_text = "\n".join(lines)

    # If schedule already extracted from first message, show post/schedule options
    # If not, show post now / schedule
    await send_message(phone, preview_text)
    await asyncio.sleep(0.5)

    if schedule and not data.get("scheduled_time"):
        # Parse and auto-schedule
        scheduled_time = scheduler_service.parse_schedule_time(str(schedule))
        if scheduled_time:
            draft_service.set_schedule(db, draft, scheduled_time)
            await send_buttons(
                phone,
                f"Schedule detected: {schedule}",
                [
                    {"id": "post_now",      "title": "🚀 Post Now Instead"},
                    {"id": "schedule_post", "title": f"🕐 Schedule as Detected"},
                ],
            )
            return {"success": True}

    await send_buttons(
        phone,
        "Ready to publish?",
        [
            {"id": "post_now",      "title": "🚀 Post Now"},
            {"id": "schedule_post", "title": "🕐 Schedule"},
        ],
    )
    return {"success": True}


async def _check_connections_and_proceed(phone: str, draft, user, db: Session) -> dict:
    """Check platform connections then show Post Now / Schedule."""
    from app.services.social_account_service import social_account_service

    # Always refresh from DB to get latest platform selection
    db.refresh(draft)
    platforms = (draft.extracted_data or {}).get("platforms", [])
    print(f"CHECK_CONNECTIONS: platforms={platforms} draft={draft.id}")
    if not platforms:
        await send_message(phone, "Please select at least one platform first.")
        await _send_platform_selection(phone, draft)
        return {"success": False}

    missing = social_account_service.get_missing_platforms(
        db=db, whatsapp_number=user.number, platforms=platforms
    )

    if missing:
        await send_message(
            phone,
            "⚠️ Please connect these platforms first:\n"
            + "\n".join(f"• {p.title()}" for p in missing)
            + "\n\nTap each link to connect, then tap ▶ Proceed again."
        )
        base = settings.APP_BASE_URL
        connect_urls = {
            "instagram": f"{base}/oauth/meta/connect?whatsapp_number={user.number}",
            "linkedin":  f"{base}/oauth/linkedin/connect?whatsapp_number={user.number}",
            "threads":   f"{base}/oauth/threads/connect?whatsapp_number={user.number}",
            "twitter":   f"{base}/oauth/twitter/connect?whatsapp_number={user.number}",
        }
        for p in missing:
            if p in connect_urls:
                await send_message(phone, f"🔗 Connect {p.title()}:\n{connect_urls[p]}")

        await asyncio.sleep(0.5)
        await send_buttons(phone, "After connecting:", [
            {"id": "proceed_to_post", "title": "▶ Proceed"},
        ])
        return {"success": True}

    # All connected
    data = draft.extracted_data or {}
    platforms_str = " + ".join(p.title() for p in platforms)
    schedule_hint = f"\n\nDetected schedule: {data['scheduled_time']}" if data.get("scheduled_time") else ""

    draft_service.update_step(db, draft, "ready_to_post")

    await send_buttons(
        phone,
        f"✅ All set! Ready to post on {platforms_str}:{schedule_hint}",
        [
            {"id": "post_now",      "title": "🚀 Post Now"},
            {"id": "schedule_post", "title": "🕐 Schedule"},
        ],
    )
    return {"success": True}


async def _execute_post_now(phone: str, draft, user, db: Session) -> dict:
    """Execute immediate publish. Never re-posts to already-successful platforms."""
    db.refresh(draft)

    data = draft.extracted_data or {}
    assets = draft.generated_assets or {}
    platforms = data.get("platforms", [])
    selected_images = assets.get("selected_images", [])
    video_url = assets.get("video_url")
    post_type = data.get("post_type", "post")
    caption = draft_service.get_effective_caption(draft)

    # Check which platforms already posted successfully for this draft
    from app.models.publish_job import PublishJob as PJ
    done_platforms = {
        j.platform for j in
        db.query(PJ).filter(PJ.draft_id == draft.id, PJ.status == "done").all()
    }
    pending_platforms = [p for p in platforms if p not in done_platforms]

    print(f"POST NOW: platforms={platforms} done={done_platforms} pending={pending_platforms}")

    if not pending_platforms:
        await send_message(phone, "✅ Already posted to all selected platforms!")
        draft_service.mark_completed(db, draft)
        return {"success": True}

    draft_service.mark_publishing(db, draft)

    await send_message(phone, "🚀 Publishing your post...")

    all_urls = [video_url] if video_url else selected_images

    try:
        await post_service.create_and_dispatch(
            db=db,
            user=user,
            draft=draft,
            platforms=pending_platforms,
            caption=caption,
            image_urls=all_urls,
            scheduled_time=None,
        )
        draft_service.mark_completed(db, draft)
    except Exception as e:
        print(f"POST DISPATCH ERROR: {e}")
        import traceback
        traceback.print_exc()
        draft_service.update_step(db, draft, "ready_to_post")
        await send_message(
            phone,
            f"❌ Failed to dispatch posts: {str(e)[:150]}\n\nSend *retry* to try again."
        )
    return {"success": True}


async def _execute_schedule(phone: str, draft, user, db: Session, scheduled_time) -> dict:
    """Execute scheduled publish."""
    from dateutil import parser as dateparser
    from datetime import datetime

    # Parse if string
    if isinstance(scheduled_time, str):
        try:
            from datetime import datetime
            # Try ISO format first (from str(datetime_obj))
            scheduled_time = datetime.fromisoformat(scheduled_time)
        except (ValueError, TypeError):
            try:
                from dateutil import parser as dateparser
                scheduled_time = dateparser.parse(scheduled_time, fuzzy=True)
            except Exception:
                scheduled_time = scheduler_service.parse_schedule_time(scheduled_time)

    if not scheduled_time:
        await send_message(phone, "Could not parse schedule time. Please try again.")
        return {"success": False}

    data = draft.extracted_data or {}
    assets = draft.generated_assets or {}
    platforms = data.get("platforms", [])
    selected_images = assets.get("selected_images", [])
    caption = draft_service.get_effective_caption(draft)

    await post_service.create_and_dispatch(
        db=db,
        user=user,
        draft=draft,
        platforms=platforms,
        caption=caption,
        image_urls=selected_images,
        scheduled_time=scheduled_time,
    )

    draft_service.mark_completed(db, draft)

    platforms_str = " + ".join(p.title() for p in platforms)
    # Convert UTC back to IST for display
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    ist_time = scheduled_time.replace(tzinfo=timezone.utc).astimezone(ist)
    formatted = ist_time.strftime("%d %b %Y at %I:%M %p")
    await send_message(
        phone,
        f"✅ Post scheduled!\n\n"
        f"📅 Time: {formatted} (IST)\n"
        f"📱 Platforms: {platforms_str}"
    )
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# RESUME / DISCARD FLOW
# ──────────────────────────────────────────────────────────────

async def _show_resume_prompt(phone: str, draft, db: Session) -> dict:
    """Show existing draft and ask to resume or discard."""
    summary = draft_service.get_progress_summary(draft)

    await send_message(
        phone,
        f"📋 You have an unfinished draft:\n\n{summary}"
    )
    await asyncio.sleep(0.5)
    await send_buttons(
        phone,
        "What would you like to do?",
        [
            {"id": "resume_draft",    "title": "▶ Continue"},
            {"id": "discard_permanently", "title": "🗑 Discard"},
        ],
    )
    return {"success": True}




async def _proceed_after_post_type(phone: str, draft, user, db: Session) -> dict:
    """After post type is confirmed, check platform then connections."""
    db.refresh(draft)
    data = draft.extracted_data or {}
    platforms = data.get("platforms") or []
    schedule = data.get("schedule") or data.get("scheduled_time")

    if not platforms:
        draft_service.update_step(db, draft, "platform_selection")
        await send_message(phone, "Almost done! Where do you want to post?")
        await asyncio.sleep(0.3)
        await _send_platform_selection(phone, draft)
        return {"success": True}

    draft_service.update_step(db, draft, "platform_selection")

    if schedule:
        scheduled_time = scheduler_service.parse_schedule_time(str(schedule))
        if scheduled_time:
            return await _execute_schedule(phone, draft, user, db, scheduled_time)

    return await _check_connections_and_proceed(phone, draft, user, db)


async def _handle_generate_image_request(phone: str, subject: str, user, db: Session) -> dict:
    """User asks to generate an image — generate it and ask if they want to post it."""
    await send_message(phone, f"🎨 Generating image of: {subject}...")

    try:
        from app.integrations.image_provider import generate_images
        images = generate_images(subject, 1)
        image_url = images[0] if images else None

        if not image_url:
            await send_message(phone, "Could not generate image. Please try again.")
            return {"success": False}

        await send_image(phone, image_url, subject)
        await asyncio.sleep(0.5)

        # Create a draft with this image ready
        draft = draft_service.create_draft(db, user)
        draft_service.update_extracted_data(db, draft, {"topic": subject})
        draft_service.set_generated_images(db, draft, [image_url])
        draft_service.set_selected_images(db, draft, [image_url])
        draft_service.update_step(db, draft, "caption_review")

        # Generate caption
        caption = await generate_caption(subject)
        draft_service.set_caption(db, draft, caption)

        await send_message(phone, f"📝 *Caption:*\n\n{caption}")
        await asyncio.sleep(0.5)
        await send_buttons(
            phone,
            "Want to post this image?",
            [
                {"id": "quick_post",      "title": "🚀 Post This"},
                {"id": "caption_edit",    "title": "✏️ Edit Caption"},
                {"id": "regenerate_imgs", "title": "🔄 Generate New"},
            ],
        )
    except Exception as e:
        print(f"IMAGE GEN REQUEST ERROR: {e}")
        await send_message(phone, "Something went wrong generating the image. Please try again.")

    return {"success": True}


async def _handle_post_history(phone: str, user, db: Session) -> dict:
    """Show user their recent posts."""
    from app.models.user_post import UserPost
    posts = (
        db.query(UserPost)
        .filter(
            UserPost.user_id == user.id,
            UserPost.status == "published",
        )
        .order_by(UserPost.published_at.desc())
        .limit(5)
        .all()
    )

    if not posts:
        await send_message(
            phone,
            "You haven't published any posts yet.\n\nSend me a topic to create your first post!"
        )
        return {"success": True}

    lines = ["📊 *Your recent posts:*\n"]
    for i, post in enumerate(posts, 1):
        caption_preview = (post.caption or "")[:50]
        if len(post.caption or "") > 50:
            caption_preview += "..."
        date = post.published_at.strftime("%d %b %Y") if post.published_at else "Unknown"
        lines.append(f"{i}. {date} — {caption_preview}")

    await send_message(phone, "\n".join(lines))
    return {"success": True}


async def _handle_cancel_schedule(phone: str, user, db: Session) -> dict:
    """Show pending scheduled posts and allow cancellation."""
    from app.models.publish_job import PublishJob
    from datetime import datetime

    jobs = (
        db.query(PublishJob)
        .filter(
            PublishJob.user_id == user.id,
            PublishJob.status == "pending",
            PublishJob.scheduled_time != None,
            PublishJob.scheduled_time > datetime.utcnow(),
        )
        .order_by(PublishJob.scheduled_time.asc())
        .all()
    )

    if not jobs:
        await send_message(phone, "You have no scheduled posts.")
        return {"success": True}

    # Group by post_id
    seen_posts = set()
    unique_jobs = []
    for j in jobs:
        if j.post_id not in seen_posts:
            seen_posts.add(j.post_id)
            unique_jobs.append(j)

    lines = ["📅 *Your scheduled posts:*\n"]
    for i, job in enumerate(unique_jobs[:3], 1):
        from app.services.scheduler_service import scheduler_service
        time_str = scheduler_service.format_ist(job.scheduled_time)
        lines.append(f"{i}. {time_str}")

    lines.append("\nTo cancel, send: *cancel post 1* (or 2, 3...)")
    await send_message(phone, "\n".join(lines))
    return {"success": True}


async def _show_discard_confirmation(phone: str, draft, db: Session) -> dict:
    """Show discard confirmation with 3 options."""
    summary = draft_service.get_progress_summary(draft)

    await send_message(
        phone,
        f"⚠️ You have an unfinished draft:\n\n{summary}\n\n"
        "Are you sure you want to discard?"
    )
    await asyncio.sleep(0.5)
    await send_buttons(
        phone,
        "Choose an option:",
        [
            {"id": "continue_editing",    "title": "✏️ Keep Editing"},
            {"id": "save_and_exit",       "title": "💾 Save & Exit"},
            {"id": "discard_permanently", "title": "🗑 Discard"},
        ],
    )
    return {"success": True}


async def _resume_draft(phone: str, draft, user, db: Session) -> dict:
    """Resume draft from exact last step."""
    db.refresh(draft)
    step = draft.current_step
    assets = draft.generated_assets or {}
    has_video = bool(assets.get("video_url"))

    print(f"RESUMING from step: {step}")
    await send_message(phone, "✅ Resuming your draft...")

    if step == "entity_extraction" or step == "collecting_missing":
        missing = get_missing_fields(draft.extracted_data or {})
        if missing:
            from app.services.entity_extraction_service import build_missing_fields_message
            await send_message(phone, build_missing_fields_message(missing))
            if missing == ["image_count"]:
                await _send_image_count_buttons(phone)
        else:
            await _proceed_to_image_generation(phone, draft, user, db)

    elif step == "image_generation":
        await _proceed_to_image_generation(phone, draft, user, db)

    elif step == "image_selection":
        images = assets.get("generated_images", [])
        if images:
            await send_message(phone, "Here are your previously generated images:")
            for i, url in enumerate(images):
                await send_image(phone, url, f"Image {i+1}")
                await asyncio.sleep(0.5)
            await _send_image_pick_buttons(phone, images)
        else:
            await _proceed_to_image_generation(phone, draft, user, db)

    elif step == "caption_review":
        await _show_caption(phone, draft, db)

    elif step == "caption_edit":
        await send_message(phone, "✏️ Send your new caption:")

    elif step == "post_type_selection":
        await _send_post_type_selection(phone, has_video=has_video)

    elif step == "platform_selection":
        await _send_platform_selection(phone, draft)

    elif step == "schedule_input":
        await send_message(phone, "📅 When should I post? (e.g. tomorrow 9am, after 2 hours)")

    elif step == "ready_to_post":
        await _check_connections_and_proceed(phone, draft, user, db)

    else:
        # Unknown step — show platform selection
        await _send_platform_selection(phone, draft)

    return {"success": True}


async def _show_resume_step(phone: str, draft, db: Session) -> dict:
    """Show what step we're on and what's needed."""
    data = draft.extracted_data or {}
    missing = get_missing_fields(data)

    if missing:
        msg = build_missing_fields_message(missing)
        await send_message(phone, msg)
        if missing == ["image_count"]:
            await _send_image_count_buttons(phone)
    else:
        await send_message(phone, "Ready to generate your images!")
        await send_buttons(phone, "Continue?", [
            {"id": "proceed_to_post", "title": "▶ Generate Images"},
        ])
    return {"success": True}


async def _resume_image_selection(phone: str, draft, db: Session) -> dict:
    assets = draft.generated_assets or {}
    images = assets.get("generated_images", [])
    if not images:
        # Need to regenerate
        return await _show_resume_step(phone, draft, db)
    await send_message(phone, "Here are your previously generated images:")
    for i, img_url in enumerate(images):
        await send_image(phone, img_url, f"Image {i + 1}")
        await asyncio.sleep(0.5)
    await _send_image_pick_buttons(phone, images)
    return {"success": True}


async def _send_message_and_return(phone: str, msg: str) -> dict:
    await send_message(phone, msg)
    return {"success": True}


async def _send_platform_selection_and_return(phone: str, draft) -> dict:
    await _send_platform_selection(phone, draft)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# UI HELPERS
# ──────────────────────────────────────────────────────────────


async def _handle_generate_image_request(phone: str, subject: str, user, db: Session) -> dict:
    """User asks to generate an image — generate it and ask if they want to post it."""
    await send_message(phone, f"🎨 Generating image of: {subject}...")

    try:
        images = generate_images(subject, 1)
        if not images:
            await send_message(phone, "Could not generate image. Please try again.")
            return {"success": False}

        image_url = images[0]
        await send_image(phone, image_url, subject)
        await asyncio.sleep(0.5)

        # Create draft with this image pre-selected
        draft = draft_service.create_draft(db, user)
        draft_service.update_extracted_data(db, draft, {"topic": subject, "image_count": 1})
        draft_service.set_generated_images(db, draft, [image_url])
        draft_service.set_selected_images(db, draft, [image_url])
        draft_service.update_generated_assets(db, draft, {"user_image": True})

        await send_buttons(
            phone,
            "Want to post this image?",
            [
                {"id": "caption_proceed", "title": "📤 Yes, Post This"},
                {"id": "regenerate_imgs", "title": "🔄 Generate New"},
                {"id": "discard_permanently", "title": "🗑 No Thanks"},
            ],
        )
        draft_service.update_step(db, draft, "caption_review")

        # Generate caption in background
        caption = await generate_caption(subject)
        draft_service.set_caption(db, draft, caption)

    except Exception as e:
        print(f"IMAGE GEN ERROR: {e}")
        await send_message(phone, "Could not generate image. Please try again.")

    return {"success": True}


async def _handle_post_history(phone: str, user, db: Session) -> dict:
    """Show user's recent posts."""
    from app.models.user_post import UserPost
    from app.models.publish_job import PublishJob

    posts = (
        db.query(UserPost)
        .filter(
            UserPost.user_id == user.id,
            UserPost.status == "published",
        )
        .order_by(UserPost.published_at.desc())
        .limit(5)
        .all()
    )

    if not posts:
        await send_message(
            phone,
            "You haven't posted anything yet.\n\nSend me a topic to create your first post!"
        )
        return {"success": True}

    lines = ["📊 *Your recent posts:*\n"]
    for i, post in enumerate(posts, 1):
        caption_preview = (post.caption or "")[:50]
        if len(post.caption or "") > 50:
            caption_preview += "..."
        date = post.published_at.strftime("%d %b %Y") if post.published_at else "Unknown"
        platforms = post.platform_type or "Unknown"
        lines.append(f"{i}. {caption_preview}\n   📱 {platforms} • 📅 {date}")

    await send_message(phone, "\n\n".join(lines))
    return {"success": True}


async def _handle_cancel_schedule(phone: str, user, db: Session) -> dict:
    """Show pending scheduled posts and allow cancellation."""
    from app.models.publish_job import PublishJob
    from datetime import datetime

    jobs = (
        db.query(PublishJob)
        .filter(
            PublishJob.user_id == user.id,
            PublishJob.status == "pending",
            PublishJob.scheduled_time != None,
            PublishJob.scheduled_time > datetime.utcnow(),
        )
        .order_by(PublishJob.scheduled_time.asc())
        .all()
    )

    if not jobs:
        await send_message(phone, "You have no scheduled posts.")
        return {"success": True}

    # Group by draft
    seen_drafts = {}
    for job in jobs:
        key = str(job.draft_id or job.post_id)
        if key not in seen_drafts:
            seen_drafts[key] = []
        seen_drafts[key].append(job)

    lines = ["🗓 *Your scheduled posts:*\n"]
    cancel_options = []

    for i, (key, job_group) in enumerate(seen_drafts.items(), 1):
        first_job = job_group[0]
        platforms = " + ".join(j.platform.title() for j in job_group)
        ist_time = scheduler_service.format_ist(first_job.scheduled_time)
        lines.append(f"{i}. 📱 {platforms}\n   🕐 {ist_time}")
        if len(cancel_options) < 3:
            cancel_options.append({
                "id": f"cancel_job_{key}",
                "title": f"Cancel #{i}"
            })

    await send_message(phone, "\n\n".join(lines))
    await asyncio.sleep(0.5)

    if cancel_options:
        await send_buttons(phone, "Which post to cancel?", cancel_options)

    return {"success": True}


async def _send_image_count_buttons(phone: str):
    await send_buttons(
        phone,
        f"How many images? (1-{MAX_IMAGES})\n\n💡 Or send your own image in chat.",
        [
            {"id": "img_count_1", "title": "1 Image"},
            {"id": "img_count_2", "title": "2 Images"},
            {"id": "img_count_3", "title": "3 Images"},
        ],
    )
    await asyncio.sleep(0.5)
    await send_buttons(phone, "More:", [
        {"id": "img_count_4", "title": "4 Images"},
        {"id": "img_count_5", "title": "5 Images"},
    ])


async def _send_caption_actions(phone: str):
    await send_buttons(
        phone,
        "Happy with this caption?",
        [
            {"id": "caption_proceed",    "title": "✅ Proceed"},
            {"id": "caption_edit",       "title": "✏️ Edit"},
            {"id": "caption_regenerate", "title": "🔄 Regenerate"},
        ],
    )



async def _send_image_count_list(phone: str):
    """Show image count selection as a WhatsApp list — clean single tap."""
    await send_list(
        phone,
        body="How many images do you want?",
        button_label="Select Count",
        sections=[
            {
                "title": "Number of Images",
                "rows": [
                    {"id": "img_count_1", "title": "1 Image",  "description": "Single image post"},
                    {"id": "img_count_2", "title": "2 Images", "description": "Two image carousel"},
                    {"id": "img_count_3", "title": "3 Images", "description": "Three image carousel"},
                    {"id": "img_count_4", "title": "4 Images", "description": "Four image carousel"},
                    {"id": "img_count_5", "title": "5 Images", "description": "Five image carousel"},
                ],
            }
        ],
    )


async def _send_image_pick_buttons(phone: str, images: list):
    count = len(images)

    if count == 1:
        await send_buttons(phone, "Your generated image:", [
            {"id": "pick_img_0",      "title": "✅ Use This Image"},
            {"id": "regenerate_imgs", "title": "🔄 Generate New"},
        ])
        return

    individual = [
        {"id": f"pick_img_{i}", "title": f"Image {i + 1} only"}
        for i in range(count)
    ]
    rows = [individual[i:i+3] for i in range(0, len(individual), 3)]

    all_label = "✅ Use Both" if count == 2 else f"✅ Use All {count}"

    await send_buttons(
        phone,
        f"Which image(s) to use? ({count} generated):",
        rows[0]
    )
    for row in rows[1:]:
        await asyncio.sleep(0.5)
        await send_buttons(phone, "More:", row)

    await asyncio.sleep(0.5)
    await send_buttons(phone, "Or:", [
        {"id": "pick_all_imgs",   "title": all_label},
        {"id": "regenerate_imgs", "title": "🔄 Generate New"},
    ])


def _extract_count(text: str) -> int | None:
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    t = text.lower().strip()
    for word, num in word_map.items():
        if word in t.split():
            return num
    nums = re.findall(r"\b([1-5])\b", t)
    if nums:
        return int(nums[0])
    big = re.findall(r"\b([6-9]|[1-9]\d+)\b", t)
    if big:
        return -1
    return None