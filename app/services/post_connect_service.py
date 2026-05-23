"""
Called after any platform OAuth connect completes.
Checks if all user's selected platforms are now connected
and sends the appropriate WhatsApp message.
"""
from sqlalchemy.orm import Session
from app.integrations.whatsapp.whatsapp_client import send_message_sync, send_buttons_sync
from app.services.session_service import session_service
from app.services.social_account_service import social_account_service


def on_platform_connected(
    db: Session,
    whatsapp_number: str,
    platform: str,
):
    """
    Called right after a platform is connected via OAuth.
    - If all selected platforms are now connected → show Post Now / Schedule
    - If some still missing → show remaining connect links
    - If no pending post → just confirm connection
    """

    # Get what platforms the user had selected for their pending post
    selected = session_service.get_selected_platforms(whatsapp_number)
    pending = session_service.get_pending_post(whatsapp_number)

    print(f"ON CONNECT: {platform} connected | selected={selected} | pending={bool(pending)}")

    # No pending post — just confirm
    if not pending or not selected:
        send_message_sync(
            whatsapp_number,
            f"✅ {platform.title()} connected successfully!"
        )
        return

    # Check which selected platforms are still missing
    still_missing = social_account_service.get_missing_platforms(
        db=db,
        whatsapp_number=whatsapp_number,
        platforms=selected,
    )
    # Remove the one just connected (in case DB not refreshed yet)
    still_missing = [p for p in still_missing if p != platform]

    if still_missing:
        # Still some platforms to connect
        from app.core.config import settings
        base = settings.APP_BASE_URL

        connect_urls = {
            "instagram": f"{base}/oauth/meta/connect?whatsapp_number={whatsapp_number}",
            "linkedin":  f"{base}/oauth/linkedin/connect?whatsapp_number={whatsapp_number}",
            "threads":   f"{base}/oauth/threads/connect?whatsapp_number={whatsapp_number}",
            "twitter":   f"{base}/oauth/twitter/connect?whatsapp_number={whatsapp_number}",
        }

        missing_str = " + ".join(p.title() for p in still_missing)
        send_message_sync(
            whatsapp_number,
            f"✅ {platform.title()} connected!\n\n"
            f"Still need to connect: *{missing_str}*"
        )
        for p in still_missing:
            if p in connect_urls:
                send_message_sync(
                    whatsapp_number,
                    f"🔗 Connect {p.title()}:\n{connect_urls[p]}"
                )
    else:
        # All platforms connected — show Post Now / Schedule
        platforms_str = " + ".join(p.title() for p in selected)
        send_message_sync(
            whatsapp_number,
            f"✅ {platform.title()} connected!\n\n"
            f"All platforms ready: *{platforms_str}*"
        )
        send_buttons_sync(
            whatsapp_number,
            f"Ready to post on {platforms_str}:",
            [
                {"id": "post_now",      "title": "🚀 Post Now"},
                {"id": "schedule_post", "title": "🕐 Schedule"},
            ],
        )