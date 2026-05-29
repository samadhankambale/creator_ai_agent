"""
Called after any platform OAuth connect completes.
Sends ONE clean message — not multiple separate messages.
Only checks platforms user actually selected.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.publish_job import PublishJob
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
    # Deduplicate — ignore if same platform connected within last 10 seconds
    import redis as _redis_lib
    from app.core.config import settings as _cfg
    try:
        _r = _redis_lib.from_url(_cfg.REDIS_URL)
        _key = f"connected:{whatsapp_number}:{platform}"
        if _r.get(_key):
            print(f"POST_CONNECT: duplicate callback ignored for {platform}")
            return
        _r.setex(_key, 10, "1")
    except Exception as _e:
        print(f"POST_CONNECT dedup error: {_e}")

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
    print(f"POST_CONNECT: platform={platform} selected={selected} draft_id={draft.id}")
    print(f"POST_CONNECT: full extracted_data={draft.extracted_data}")

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
        # All selected platforms now connected
        platforms_str = " + ".join(p.title() for p in selected)

        # Check if there are pending scheduled jobs — dispatch them now
        # Check for awaiting_connection jobs (scheduled but platform wasn't connected)
        # and regular pending jobs
        # Search by user + platform, not just draft_id
        # In case draft changed between scheduling and connecting
        waiting_jobs = (
            db.query(PublishJob)
            .filter(
                PublishJob.user_id == user.id,
                PublishJob.status == "awaiting_connection",
                PublishJob.platform == platform,
            )
            .all()
        )
        # Also check draft-specific ones
        draft_waiting = (
            db.query(PublishJob)
            .filter(
                PublishJob.draft_id == draft.id,
                PublishJob.status == "awaiting_connection",
            )
            .all()
        )
        # Combine and deduplicate
        seen_ids = set()
        combined = []
        for j in waiting_jobs + draft_waiting:
            if str(j.id) not in seen_ids:
                seen_ids.add(str(j.id))
                combined.append(j)
        waiting_jobs = combined
        pending_jobs = (
            db.query(PublishJob)
            .filter(
                PublishJob.draft_id == draft.id,
                PublishJob.status == "pending",
            )
            .all()
        )

        # Check if any selected platforms still need connection
        still_missing_after = [
            p for p in selected
            if not social_account_service.get(db, user.id, p)
        ]

        if still_missing_after:
            # Still more platforms to connect — already shown in still_missing block above
            pass
        elif waiting_jobs:
            # All connected — show Post Now button (don't auto-post)
            from app.workers.scheduled_post_worker import execute_publish_job
            # Reset waiting jobs back to pending so they can be dispatched
            for j in waiting_jobs:
                j.status = "pending"
                db.commit()
            send_message_sync(
                whatsapp_number,
                f"✅ {platform.title()} connected!\n\n"
                f"All platforms ready: *{platforms_str}*"
            )
            send_buttons_sync(
                whatsapp_number,
                "What would you like to do?",
                [
                    {"id": "post_now",      "title": "🚀 Post Now"},
                    {"id": "schedule_post", "title": "🕐 Schedule"},
                ],
            )
        elif pending_jobs:
            immediate = [j for j in pending_jobs if not j.scheduled_time]
            scheduled = [j for j in pending_jobs if j.scheduled_time]
            if immediate:
                from app.workers.scheduled_post_worker import execute_publish_job
                for j in immediate:
                    execute_publish_job.delay(str(j.id))
                send_message_sync(
                    whatsapp_number,
                    f"✅ {platform.title()} connected!\n\n"
                    f"🚀 Publishing to {platforms_str} now..."
                )
            elif scheduled:
                from app.services.scheduler_service import scheduler_service
                job = scheduled[0]
                time_str = scheduler_service.format_ist(job.scheduled_time)
                send_message_sync(
                    whatsapp_number,
                    f"✅ {platform.title()} connected!\n\n"
                    f"📅 Your post is scheduled for {time_str} on {platforms_str}."
                )
        else:
            # No jobs — check if user was trying to schedule
            pending_action = (draft.extracted_data or {}).get("pending_action")
            if pending_action == "schedule":
                # User was trying to schedule — ask for time now
                draft.current_step = "schedule_input"
                db.commit()
                send_message_sync(
                    whatsapp_number,
                    f"✅ {platform.title()} connected!\n\n"
                    f"All platforms ready: *{platforms_str}*\n\n"
                    "📅 When should I post?\n\nExamples:\n- tomorrow 9am\n- after 2 hours\n- tonight 8pm"
                )
            else:
                if draft.draft_status == "failed":
                    draft.draft_status = "active"
                    draft.current_step = "ready_to_post"
                    db.commit()
                send_message_sync(
                    whatsapp_number,
                    f"✅ {platform.title()} connected!\n\n"
                    f"All platforms ready: *{platforms_str}*"
                )
                send_buttons_sync(
                    whatsapp_number,
                    "What would you like to do?",
                    [
                        {"id": "post_now",      "title": "🚀 Post Now"},
                        {"id": "schedule_post", "title": "🕐 Schedule"},
                    ],
                )