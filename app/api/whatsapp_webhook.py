import asyncio
import traceback
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

PLATFORMS = ["instagram", "linkedin", "threads"]


# ──────────────────────────────────────────────────────────────
# VERIFY
# ──────────────────────────────────────────────────────────────

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        print("WEBHOOK VERIFIED")
        return int(challenge)
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
            print("=" * 40)
            print("WEBHOOK HIT")
            print("=" * 40)

            entry = payload.get("entry", [])
            if not entry:
                return {"success": True}

            changes = entry[0].get("changes", [])
            if not changes:
                return {"success": True}

            value = changes[0].get("value", {})

            if "messages" not in value:
                print("NO MESSAGE FOUND")
                return {"success": True}

            message = value["messages"][0]
            contacts = value.get("contacts", [])
            if not contacts:
                return {"success": True}

            phone = contacts[0].get("wa_id")
            print("FROM:", phone)

            if message.get("type") == "interactive":
                return await _handle_button(phone, message, db)

            if message.get("type") == "text":
                text = message["text"].get("body", "").strip()
                return await _handle_text(phone, text, db)

            return {"success": True}

        except Exception as e:
            print("WEBHOOK ERROR:", str(e))
            traceback.print_exc()
            return {"success": False}


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

    # ── Platform toggle ───────────────────────────────
    if button_id.startswith("platform_"):
        platform = button_id.replace("platform_", "")

        selected = session_service.get_selected_platforms(phone)

        # Toggle: add if not selected, remove if already selected
        if platform in selected:
            selected.remove(platform)
            action = "deselected"
        else:
            selected.append(platform)
            action = "selected"

        session_service.save_selected_platforms(phone, selected)

        pending = session_service.get_pending_post(phone)
        if pending:
            pending["platforms"] = selected
            session_service.save_pending_post(phone, pending)

        # Build status line showing what's currently selected
        if selected:
            selected_str = " + ".join(p.title() for p in selected)
            body = f"Selected: {selected_str}"
        else:
            body = "No platforms selected"

        await send_buttons(
            phone,
            body,
            [
                {"id": "post_now", "title": "Post Now"},
                {"id": "schedule_post", "title": "Schedule"},
            ],
        )
        return {"success": True}

    # ── Post Now ──────────────────────────────────────
    if button_id == "post_now":
        pending = session_service.get_pending_post(phone)
        if not pending:
            await send_message(phone, "No pending post. Send me content to create a new post.")
            return {"success": False}

        selected = session_service.get_selected_platforms(phone)
        if not selected:
            await send_message(
                phone,
                "No platform selected. Please choose at least one platform first."
            )
            # Re-send platform selection buttons
            await _send_platform_buttons(phone, selected)
            return {"success": False}

        # Check which platforms are not connected
        missing = post_service.get_missing_platforms(
            db=db,
            whatsapp_number=phone,
            platforms=selected,
        )

        if missing:
            for platform in missing:
                connect_url = _get_connect_url(phone, platform)
                if connect_url:
                    await send_message(
                        phone,
                        f"⚠️ {platform.title()} not connected.\n\nTap to connect:\n{connect_url}",
                    )
            return {"success": True}

        # All connected — dispatch jobs for ALL selected platforms
        post_service.create_immediate_publish_jobs(
            db=db,
            whatsapp_number=phone,
            pending_post=pending,
            platforms=selected,
        )
        session_service.clear_all(phone)

        platforms_str = " + ".join(p.title() for p in selected)
        await send_message(
            phone,
            f"🚀 Publishing to {platforms_str}... you'll get a confirmation shortly."
        )
        return {"success": True}

    # ── Schedule ──────────────────────────────────────
    if button_id == "schedule_post":
        selected = session_service.get_selected_platforms(phone)
        if not selected:
            await send_message(phone, "Please select a platform first.")
            await _send_platform_buttons(phone, selected)
            return {"success": False}

        session_service.set_waiting_for_schedule(phone, True)
        await send_message(
            phone,
            "When should I post?\n\nExamples:\n- tomorrow 9am\n- after 2 hours\n- tonight 8pm",
        )
        return {"success": True}

    return {"success": True}


# ──────────────────────────────────────────────────────────────
# TEXT HANDLER
# ──────────────────────────────────────────────────────────────

async def _handle_text(phone: str, text: str, db: Session) -> dict:

    # ── Waiting for schedule time ─────────────────────
    if session_service.is_waiting_for_schedule(phone):
        scheduled_time = scheduler_service.parse_schedule_time(text)

        if not scheduled_time:
            await send_message(
                phone,
                "I couldn't understand that time. Try 'tomorrow 9am' or 'after 2 hours'.",
            )
            return {"success": False}

        pending = session_service.get_pending_post(phone)
        platforms = session_service.get_selected_platforms(phone)

        post_service.create_scheduled_publish_jobs(
            db=db,
            whatsapp_number=phone,
            pending_post=pending,
            platforms=platforms,
            scheduled_time=scheduled_time,
        )
        session_service.clear_all(phone)

        platforms_str = " + ".join(p.title() for p in platforms)
        formatted = scheduled_time.strftime("%d %b %Y at %I:%M %p")
        await send_message(
            phone,
            f"✅ Post scheduled for {formatted} (IST) on {platforms_str}"
        )
        return {"success": True}

    # ── Generate AI post ──────────────────────────────
    await send_message(phone, "✨ Creating your post...")

    ai_post = await post_service.create_ai_post(db, phone, text)
    print("AI POST:", ai_post)

    session_service.save_pending_post(phone, ai_post)
    session_service.save_selected_platforms(phone, [])  # reset selection

    await send_image(phone, ai_post["image_url"], ai_post["caption"])
    await asyncio.sleep(1)

    # Show platform selection — WhatsApp max 3 buttons
    await _send_platform_buttons(phone, [])
    return {"success": True}


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

async def _send_platform_buttons(phone: str, selected: list):
    """
    Send platform selection buttons.
    Shows tick on already-selected platforms.
    WhatsApp only allows 3 buttons max.
    """
    def label(p):
        tick = "✓ " if p in selected else ""
        return f"{tick}{p.title()}"

    await send_buttons(
        phone,
        "Choose platform(s) — tap to select, then Post Now",
        [
            {"id": "platform_instagram", "title": label("instagram")},
            {"id": "platform_linkedin",  "title": label("linkedin")},
            {"id": "platform_threads",   "title": label("threads")},
        ],
    )


def _get_connect_url(phone: str, platform: str) -> str | None:
    base = settings.APP_BASE_URL
    if platform == "instagram":
        return f"{base}/oauth/meta/connect?whatsapp_number={phone}"
    elif platform == "linkedin":
        return f"{base}/oauth/linkedin/connect?whatsapp_number={phone}"
    elif platform == "threads":
        return f"{base}/oauth/threads/connect?whatsapp_number={phone}"
    return None