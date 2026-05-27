"""
Called after any platform OAuth connect completes.
Sends ONE clean message — not multiple separate messages.
Only checks platforms user actually selected.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.integrations.whatsapp.whatsapp_client import send_message_sync, send_buttons_sync
from app.services.social_account_service import social_account_service
from app.services.user_service import user_service


def _connect_url(base: str, platform: str, whatsapp_number: str) -> str:
    urls = {
        "instagram": f"{base}/oauth/meta/connect?whatsapp_number={whatsapp_number}",
        "linkedin":  f"{base}/oauth/linkedin/connect?whatsapp_number={whatsapp_number}",
        "threads":   f"{base}/oauth/threads/connect?whatsapp_number={whatsapp_number}",
        "twitter":   f"{base}/oauth/twitter/connect?whatsapp_number={whatsapp_number}",
    }
    return urls.get(platform, "")


def on_platform_connected(db: Session, whatsapp_number: str, platform: str):
    user = user_service.get_by_number(db, whatsapp_number)
    if not user:
        send_message_sync(whatsapp_number, f"✅ {platform.title()} connected!")
        return

    # Find most recent active/failed draft within 2 hours
    from app.models.draft import Draft
    cutoff = datetime.utcnow() - timedelta(hours=2)
    draft = (
        db.query(Draft)
        .filter(
            Draft.user_id == user.id,
            Draft.draft_status.in_(["active", "failed"]),
            Draft.updated_at >= cutoff,
        )
        .order_by(Draft.updated_at.desc())
        .first()
    )

    if not draft:
        send_message_sync(whatsapp_number, f"✅ {platform.title()} connected!")
        return

    db.refresh(draft)
    selected = (draft.extracted_data or {}).get("platforms") or []
    print(f"POST_CONNECT: platform={platform} selected={selected}")

    if not selected:
        send_message_sync(whatsapp_number, f"✅ {platform.title()} connected!")
        return

    # Force fresh DB read before checking
    db.expire_all()

    # Check which selected platforms are still missing (excluding just-connected one)
    still_missing = []
    for p in selected:
        if p == platform:
            continue  # just connected this one
        account = social_account_service.get(db, user.id, p)
        if not account:
            still_missing.append(p)
            print(f"POST_CONNECT: {p} NOT connected")
        else:
            print(f"POST_CONNECT: {p} is connected")

    print(f"POST_CONNECT: still_missing={still_missing}")

    from app.core.config import settings
    base = settings.APP_BASE_URL

    if still_missing:
        # ONE message with all remaining links
        missing_str = " + ".join(p.title() for p in still_missing)
        links = "\n".join(
            f"🔗 {p.title()}: {_connect_url(base, p, whatsapp_number)}"
            for p in still_missing
        )
        send_message_sync(
            whatsapp_number,
            f"✅ {platform.title()} connected!\n\n"
            f"Still need to connect: *{missing_str}*\n\n"
            f"{links}"
        )
    else:
        # All connected — reactivate draft and show Post Now / Schedule
        if draft.draft_status == "failed":
            draft.draft_status = "active"
            draft.current_step = "ready_to_post"
            db.commit()

        platforms_str = " + ".join(p.title() for p in selected)
        send_message_sync(
            whatsapp_number,
            f"✅ {platform.title()} connected!\n\n"
            f"All platforms ready: *{platforms_str}*\n\n"
            "Your draft is saved — ready to publish! 🎉"
        )
        send_buttons_sync(
            whatsapp_number,
            "What would you like to do?",
            [
                {"id": "post_now",      "title": "🚀 Post Now"},
                {"id": "schedule_post", "title": "🕐 Schedule"},
            ],
        )