import asyncio
import traceback
import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database.dependencies import get_db
from app.core.config import settings
from app.integrations.whatsapp.whatsapp_client import send_message, send_buttons, send_image
from app.services.post_service import post_service
from app.services.session_service import session_service
from app.services.scheduler_service import scheduler_service

router = APIRouter(tags=["WhatsApp Webhook"])
webhook_lock = asyncio.Lock()

ALL_PLATFORMS = ["instagram", "linkedin", "threads", "twitter"]

# ── States ────────────────────────────────────────────────────
STATE_IDLE            = "idle"
STATE_WAITING_COUNT   = "waiting_count"
STATE_WAITING_IMGSEL  = "waiting_imgsel"
STATE_WAITING_SCHED   = "waiting_sched"


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
            print(f"\n{'='*40}\nFROM: {phone} | TYPE: {msg_type}\n{'='*40}")

            if msg_type == "image":
                return await _handle_user_image(phone, message, db)
            if msg_type == "interactive":
                return await _handle_button(phone, message, db)
            if msg_type == "text":
                return await _handle_text(phone, message["text"].get("body", "").strip(), db)

            return {"success": True}

        except Exception as e:
            print("WEBHOOK ERROR:", e)
            traceback.print_exc()
            return {"success": False}


# ──────────────────────────────────────────────────────────────
# STEP 0 — User sends own image
# ──────────────────────────────────────────────────────────────

async def _handle_user_image(phone: str, message: dict, db: Session) -> dict:
    media_id = message.get("image", {}).get("id")
    caption_text = message.get("image", {}).get("caption", "").strip()

    if not media_id:
        await send_message(phone, "Could not read image. Please try again.")
        return {"success": False}

    await send_message(phone, "📸 Got your image! Generating caption...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://graph.facebook.com/v20.0/{media_id}",
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
        image_url = resp.json().get("url")
        if not image_url:
            await send_message(phone, "Could not download image. Please try again.")
            return {"success": False}

        prompt = session_service.get_pending_prompt(phone) or caption_text or "social media post"
        caption = await post_service.generate_caption_only(prompt)

        # Save and go straight to platform selection
        pending = post_service.save_post_with_images(
            db=db, whatsapp_number=phone,
            user_message=prompt, caption=caption, image_urls=[image_url],
        )
        session_service.clear_all(phone)
        session_service.save_pending_post(phone, pending)

        await send_image(phone, image_url, caption)
        await asyncio.sleep(1)
        await _send_platform_selection(phone, [])

    except Exception as e:
        print("USER IMAGE ERROR:", e)
        traceback.print_exc()
        await send_message(phone, "Something went wrong. Please try again.")

    return {"success": True}


# ──────────────────────────────────────────────────────────────
# BUTTON HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_button(phone: str, message: dict, db: Session) -> dict:
    button_id = (
        message.get("interactive", {})
        .get("button_reply", {})
        .get("id", "")
    )
    print("BUTTON:", button_id)

    # ── STEP 2: Image count ───────────────────────────
    if button_id.startswith("img_count_"):
        state = session_service.get_state(phone)
        if state != STATE_WAITING_COUNT:
            return {"success": True}
        count = int(button_id.replace("img_count_", ""))
        if count > 5:
            await send_message(phone, "Maximum 5 images. Please choose 1-5.")
            await _send_image_count_buttons(phone)
            return {"success": True}
        await _generate_and_show_images(phone, count)
        return {"success": True}

    # ── STEP 3: Pick single image ─────────────────────
    if button_id.startswith("pick_img_"):
        state = session_service.get_state(phone)
        if state != STATE_WAITING_IMGSEL:
            return {"success": True}
        index = int(button_id.replace("pick_img_", ""))
        images = session_service.get_generated_images(phone)
        if not images or index >= len(images):
            await send_message(phone, "Selection expired. Send your topic again.")
            return {"success": False}
        return await _confirm_image_selection(phone, [images[index]], db)

    # ── STEP 3: Pick all images ───────────────────────
    if button_id == "pick_all_imgs":
        state = session_service.get_state(phone)
        if state != STATE_WAITING_IMGSEL:
            return {"success": True}
        images = session_service.get_generated_images(phone)
        if not images:
            await send_message(phone, "Selection expired. Send your topic again.")
            return {"success": False}
        return await _confirm_image_selection(phone, images, db)

    # ── STEP 3: Regenerate ────────────────────────────
    if button_id == "regenerate_imgs":
        state = session_service.get_state(phone)
        if state != STATE_WAITING_IMGSEL:
            return {"success": True}
        images = session_service.get_generated_images(phone)
        count = len(images) if images else 1
        session_service.delete_generated_images(phone)
        await send_message(phone, f"🔄 Generating {count} fresh image(s)...")
        await _generate_and_show_images(phone, count)
        return {"success": True}

    # ── STEP 4: Platform toggle ───────────────────────
    if button_id.startswith("platform_"):
        platform = button_id.replace("platform_", "")
        selected = session_service.get_selected_platforms(phone)
        if platform in selected:
            selected.remove(platform)
        else:
            selected.append(platform)
        session_service.save_selected_platforms(phone, selected)
        pending = session_service.get_pending_post(phone)
        if pending:
            pending["platforms"] = selected
            session_service.save_pending_post(phone, pending)
        await _send_platform_selection(phone, selected)
        return {"success": True}

    # ── STEP 4: Select all platforms ─────────────────
    if button_id == "select_all":
        selected = ALL_PLATFORMS.copy()
        session_service.save_selected_platforms(phone, selected)
        pending = session_service.get_pending_post(phone)
        if pending:
            pending["platforms"] = selected
            session_service.save_pending_post(phone, pending)
        await _send_platform_selection(phone, selected)
        return {"success": True}

    # ── STEP 4: Proceed (check connections) ───────────
    if button_id == "proceed":
        return await _check_and_proceed(phone, db)

    # ── STEP 5: Post Now ──────────────────────────────
    if button_id == "post_now":
        return await _do_post_now(phone, db)

    # ── STEP 5: Schedule ──────────────────────────────
    if button_id == "schedule_post":
        selected = session_service.get_selected_platforms(phone)
        if not selected:
            await send_message(phone, "Please select at least one platform first.")
            await _send_platform_selection(phone, [])
            return {"success": False}
        session_service.set_state(phone, STATE_WAITING_SCHED)
        await send_message(
            phone,
            "📅 When should I post?\n\nExamples:\n- tomorrow 9am\n- after 2 hours\n- tonight 8pm",
        )
        return {"success": True}

    return {"success": True}


# ──────────────────────────────────────────────────────────────
# TEXT HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_text(phone: str, text: str, db: Session) -> dict:
    state = session_service.get_state(phone)
    print(f"STATE: {state}")

    # ── STEP 5b: Schedule time input ─────────────────
    if state == STATE_WAITING_SCHED:
        scheduled_time = scheduler_service.parse_schedule_time(text)
        if not scheduled_time:
            await send_message(phone, "Couldn't understand that. Try 'tomorrow 9am' or 'after 2 hours'.")
            return {"success": False}

        pending = session_service.get_pending_post(phone)
        platforms = session_service.get_selected_platforms(phone)

        post_service.create_scheduled_publish_jobs(
            db=db, whatsapp_number=phone,
            pending_post=pending, platforms=platforms,
            scheduled_time=scheduled_time,
        )
        session_service.clear_all(phone)

        platforms_str = " + ".join(p.title() for p in platforms)
        formatted = scheduled_time.strftime("%d %b %Y at %I:%M %p")
        await send_message(phone, f"✅ Scheduled for {formatted} (IST)\nPlatforms: {platforms_str}")
        return {"success": True}

    # ── STEP 2b: User typed image count ──────────────
    if state == STATE_WAITING_COUNT:
        count = _extract_count(text)
        if count == -1:
            # User asked for more than 5
            await send_message(
                phone,
                "Maximum 5 images per post. How many would you like? (1-5)"
            )
            await _send_image_count_buttons(phone)
        elif count:
            await _generate_and_show_images(phone, count)
        else:
            await send_message(phone, "Please choose how many images (1-5):")
            await _send_image_count_buttons(phone)
        return {"success": True}

    # ── STEP 1: New post topic ────────────────────────
    # Clear ALL previous state first
    session_service.clear_all(phone)
    session_service.save_pending_prompt(phone, text)
    session_service.set_state(phone, STATE_WAITING_COUNT)

    await send_message(phone, "✨ Generating caption...")
    caption = await post_service.generate_caption_only(text)
    session_service.save_pending_caption(phone, caption)

    await send_message(phone, f"📝 *Caption:*\n\n{caption}")
    await asyncio.sleep(0.5)
    await _send_image_count_buttons(phone)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# GENERATE IMAGES
# ──────────────────────────────────────────────────────────────

async def _generate_and_show_images(phone: str, count: int):
    prompt = session_service.get_pending_prompt(phone) or ""
    session_service.set_state(phone, STATE_WAITING_IMGSEL)

    await send_message(phone, f"🎨 Generating {count} image(s) with AI... Please wait.")

    try:
        images = post_service.generate_multiple_images(
            post_service.build_image_prompt(prompt), count
        )
    except Exception as e:
        print(f"IMAGE GENERATION ERROR: {e}")
        await send_message(
            phone,
            f"❌ Image generation failed:\n\n{str(e)[:300]}\n\nCheck uvicorn logs for details."
        )
        session_service.set_state(phone, "idle")
        return

    session_service.save_generated_images(phone, images)

    # Send all images
    for i, img_url in enumerate(images):
        await send_image(phone, img_url, f"Image {i + 1} of {count}")
        await asyncio.sleep(0.8)

    await asyncio.sleep(0.5)
    await _send_image_pick_buttons(phone, images)


async def _send_image_pick_buttons(phone: str, images: list):
    """
    Dynamic image selection for any count 1-5.
    WhatsApp max 3 buttons per message.
    """
    count = len(images)

    if count == 1:
        await send_buttons(
            phone, "Your generated image:",
            [
                {"id": "pick_img_0",      "title": "✅ Use This Image"},
                {"id": "regenerate_imgs", "title": "🔄 Generate New"},
            ])
        return

    # Individual pick buttons in rows of 3
    individual = [
        {"id": f"pick_img_{i}", "title": f"Image {i + 1} only"}
        for i in range(count)
    ]
    rows = [individual[i:i+3] for i in range(0, len(individual), 3)]

    await send_buttons(
        phone,
        f"Which image(s) do you want? ({count} images generated):",
        rows[0]
    )
    for row in rows[1:]:
        await asyncio.sleep(0.5)
        await send_buttons(phone, "More:", row)

    # Final row: Use All + Regenerate
    await asyncio.sleep(0.5)
    all_label = "✅ Use Both" if count == 2 else f"✅ Use All {count}"
    await send_buttons(
        phone, "Or:",
        [
            {"id": "pick_all_imgs",   "title": all_label},
            {"id": "regenerate_imgs", "title": "🔄 Generate New"},
        ])

async def _confirm_image_selection(phone: str, chosen: list, db) -> dict:
    caption = session_service.get_pending_caption(phone) or ""
    prompt = session_service.get_pending_prompt(phone) or ""

    pending = post_service.save_post_with_images(
        db=db, whatsapp_number=phone,
        user_message=prompt, caption=caption, image_urls=chosen,
    )

    session_service.save_pending_post(phone, pending)
    session_service.save_selected_platforms(phone, [])
    session_service.delete_generated_images(phone)
    session_service.delete_pending_caption(phone)
    session_service.set_state(phone, STATE_IDLE)

    count = len(chosen)
    note = "\n\n*Note:* Twitter doesn't support carousels — it will post the first image only." if count > 1 else ""
    await send_message(phone, f"✅ {count} image{'s' if count > 1 else ''} selected!{note}")
    await asyncio.sleep(0.5)
    await _send_platform_selection(phone, [])
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# PLATFORM SELECTION
# ──────────────────────────────────────────────────────────────

async def _send_platform_selection(phone: str, selected: list):
    def label(p):
        return f"✓ {p.title()}" if p in selected else p.title()

    status = (
        f"Selected: {' + '.join(p.title() for p in selected)}\nTap to add/remove:"
        if selected else "Choose platform(s) to post on:"
    )

    await send_buttons(phone, status,
        [
            {"id": "platform_instagram", "title": label("instagram")},
            {"id": "platform_linkedin",  "title": label("linkedin")},
            {"id": "platform_threads",   "title": label("threads")},
        ])
    await asyncio.sleep(0.5)
    await send_buttons(phone, "More:",
        [
            {"id": "platform_twitter", "title": label("twitter")},
            {"id": "select_all",       "title": "⭐ All Platforms"},
        ])

    if selected:
        await asyncio.sleep(0.5)
        await send_buttons(
            phone,
            f"Post to: {' + '.join(p.title() for p in selected)}",
            [{"id": "proceed", "title": "▶ Proceed"}],
        )


# ──────────────────────────────────────────────────────────────
# CHECK CONNECTIONS THEN SHOW POST/SCHEDULE
# ──────────────────────────────────────────────────────────────

async def _check_and_proceed(phone: str, db: Session) -> dict:
    pending = session_service.get_pending_post(phone)
    if not pending:
        await send_message(phone, "No pending post. Send me a topic to start.")
        return {"success": False}

    selected = session_service.get_selected_platforms(phone)
    if not selected:
        await send_message(phone, "Please select at least one platform first.")
        await _send_platform_selection(phone, [])
        return {"success": False}

    # Check which platforms are not connected at all
    missing = post_service.get_missing_platforms(
        db=db, whatsapp_number=phone, platforms=selected
    )

    if missing:
        await send_message(
            phone,
            "⚠️ These platforms are not connected yet:\n"
            + "\n".join(f"• {p.title()}" for p in missing)
            + "\n\nTap each link below to connect, then tap ▶ Proceed again."
        )
        for platform in missing:
            url = _connect_url(phone, platform)
            if url:
                await send_message(phone, f"🔗 Connect {platform.title()}:\n{url}")
        await asyncio.sleep(0.5)
        await send_buttons(phone, "After connecting all platforms:",
            [{"id": "proceed", "title": "▶ Proceed"}])
        return {"success": True}

    # All connected — show Post Now / Schedule
    platforms_str = " + ".join(p.title() for p in selected)
    await send_buttons(
        phone,
        f"✅ All set! Ready to post on {platforms_str}:",
        [
            {"id": "post_now",      "title": "🚀 Post Now"},
            {"id": "schedule_post", "title": "🕐 Schedule"},
        ],
    )
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# POST NOW
# ──────────────────────────────────────────────────────────────

async def _do_post_now(phone: str, db: Session) -> dict:
    print("=" * 40)
    print("POST NOW CALLED")
    pending = session_service.get_pending_post(phone)
    print("PENDING POST:", pending)
    selected = session_service.get_selected_platforms(phone)
    print("SELECTED PLATFORMS:", selected)
    print("=" * 40)

    if not pending:
        await send_message(phone, "No pending post. Send me a topic to start.")
        return {"success": False}

    if not selected:
        await send_message(phone, "No platforms selected.")
        return {"success": False}

    post_service.create_immediate_publish_jobs(
        db=db, whatsapp_number=phone,
        pending_post=pending, platforms=selected,
    )
    session_service.clear_all(phone)

    platforms_str = " + ".join(p.title() for p in selected)
    await send_message(
        phone,
        f"🚀 Publishing to {platforms_str}...\n"
        "You'll get a confirmation for each platform shortly."
    )
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# UI HELPERS
# ──────────────────────────────────────────────────────────────

async def _send_image_count_buttons(phone: str):
    """
    Show quick buttons for common counts.
    User can also just type any number 1-5.
    """
    await send_buttons(
        phone,
        "How many images do you want? (1-5)\n\n"
        "Tap a button or just type a number.\n"
        "💡 Or send your own image directly in chat.",
        [
            {"id": "img_count_1", "title": "1 Image"},
            {"id": "img_count_2", "title": "2 Images"},
            {"id": "img_count_3", "title": "3 Images"},
        ],
    )
    await asyncio.sleep(0.5)
    await send_buttons(
        phone,
        "More:",
        [
            {"id": "img_count_4", "title": "4 Images"},
            {"id": "img_count_5", "title": "5 Images"},
        ],
    )


def _extract_count(text: str) -> int | None:
    """Extract number 1-5 from text like '3', 'three', 'generate 3 images'."""
    import re
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    t = text.lower().strip()
    for word, num in word_map.items():
        if word in t.split():
            return num
    # Find any digit 1-5 in the text
    nums = re.findall(r"\b([1-5])\b", t)
    if nums:
        return int(nums[0])
    # Also catch numbers > 5 and warn
    big = re.findall(r"\b([6-9]|[1-9]\d+)\b", t)
    if big:
        return -1  # signal: too many
    return None


def _connect_url(phone: str, platform: str) -> str | None:
    base = settings.APP_BASE_URL
    return {
        "instagram": f"{base}/oauth/meta/connect?whatsapp_number={phone}",
        "linkedin":  f"{base}/oauth/linkedin/connect?whatsapp_number={phone}",
        "threads":   f"{base}/oauth/threads/connect?whatsapp_number={phone}",
        "twitter":   f"{base}/oauth/twitter/connect?whatsapp_number={phone}",
    }.get(platform)