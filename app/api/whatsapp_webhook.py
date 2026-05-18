import asyncio
import traceback

from fastapi import (
    APIRouter,
    Depends,
    Request
)

from sqlalchemy.orm import Session

from app.database.dependencies import (
    get_db
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message,
    send_buttons,
    send_image
)

from app.services.post_service import (
    post_service
)

from app.services.session_service import (
    session_service
)

from app.services.scheduler_service import (
    scheduler_service
)

from app.core.config import (
    settings
)


router = APIRouter()

webhook_lock = asyncio.Lock()


# =====================================================
# VERIFY WEBHOOK
# =====================================================

@router.get("/webhook")
async def verify_webhook(
    request: Request
):

    params = request.query_params

    mode = params.get("hub.mode")

    token = params.get("hub.verify_token")

    challenge = params.get("hub.challenge")

    if (
        mode == "subscribe"
        and token == "creator_ai_verify_token"
    ):

        return int(challenge)

    return {
        "error":
        "Verification failed"
    }


# =====================================================
# RECEIVE MESSAGE
# =====================================================

@router.post("/webhook")
async def receive_message(
    payload: dict,
    db: Session = Depends(get_db)
):

    async with webhook_lock:

        try:

            print("================================")
            print("WEBHOOK HIT")
            print("================================")

            print(payload)

            # =========================================
            # VALIDATE PAYLOAD
            # =========================================

            if "entry" not in payload:

                return {
                    "success":
                    False
                }

            entry = payload["entry"][0]

            changes = entry.get(
                "changes",
                []
            )

            if not changes:

                return {
                    "success":
                    False
                }

            value = changes[0].get(
                "value",
                {}
            )

            # =========================================
            # IGNORE STATUS EVENTS
            # =========================================

            if "messages" not in value:

                print(
                    "NO MESSAGE FOUND"
                )

                return {
                    "success":
                    True
                }

            message = value["messages"][0]

            contacts = value.get(
                "contacts",
                []
            )

            if not contacts:

                return {
                    "success":
                    False
                }

            phone_number = (
                contacts[0]
                .get("wa_id")
            )

            print("PHONE NUMBER:")
            print(phone_number)

            # =========================================
            # INTERACTIVE BUTTONS
            # =========================================

            if (
                message.get("type")
                == "interactive"
            ):

                interactive = (
                    message.get(
                        "interactive",
                        {}
                    )
                )

                button_reply = (
                    interactive.get(
                        "button_reply",
                        {}
                    )
                )

                button_id = (
                    button_reply.get(
                        "id"
                    )
                )

                print("BUTTON CLICK:")
                print(button_id)

                # =====================================
                # PLATFORM SELECT
                # =====================================

                if (
                    button_id.startswith(
                        "platform_"
                    )
                ):

                    platform = (
                        button_id.replace(
                            "platform_",
                            ""
                        )
                    )

                    print("PLATFORM:")
                    print(platform)

                    selected_platforms = (
                        session_service
                        .get_selected_platforms(
                            phone_number
                        )
                    )

                    if (
                        platform
                        not in selected_platforms
                    ):

                        selected_platforms.append(
                            platform
                        )

                    session_service.save_selected_platforms(

                        phone_number,

                        selected_platforms
                    )

                    print(
                        "UPDATED PLATFORMS:"
                    )

                    print(
                        selected_platforms
                    )

                    pending_post = (
                        session_service
                        .get_pending_post(
                            phone_number
                        )
                    )

                    if pending_post:

                        pending_post[
                            "platforms"
                        ] = (
                            selected_platforms
                        )

                        session_service.save_pending_post(

                            phone_number,

                            pending_post
                        )

                    await send_buttons(

                        phone_number,

                        (
                            f"{platform.title()} "
                            f"selected"
                        ),

                        [

                            {
                                "id":
                                "post_now",

                                "title":
                                "Post Now"
                            },

                            {
                                "id":
                                "schedule_post",

                                "title":
                                "Schedule"
                            }
                        ]
                    )

                    return {
                        "success":
                        True
                    }

                # =====================================
                # POST NOW
                # =====================================

                if button_id == "post_now":

                    print(
                        "POST NOW CLICKED"
                    )

                    pending_post = (
                        session_service
                        .get_pending_post(
                            phone_number
                        )
                    )

                    print("PENDING POST:")
                    print(pending_post)

                    if not pending_post:

                        await send_message(

                            phone_number,

                            (
                                "No pending post "
                                "found."
                            )
                        )

                        return {
                            "success":
                            False
                        }

                    # =================================
                    # GET SELECTED PLATFORMS
                    # =================================

                    selected_platforms = (

                        session_service
                        .get_selected_platforms(
                            phone_number
                        )
                    )

                    print(
                        "SELECTED PLATFORMS:"
                    )

                    print(
                        selected_platforms
                    )

                    print(
                        type(
                            selected_platforms
                        )
                    )

                    # =================================
                    # CHECK MISSING
                    # =================================

                    missing_platforms = (

                        post_service
                        .get_missing_platforms(

                            db=db,

                            whatsapp_number=
                            phone_number,

                            platforms=
                            selected_platforms
                        )
                    )

                    print(
                        "MISSING PLATFORMS:"
                    )

                    print(
                        missing_platforms
                    )

                    # =================================
                    # SEND CONNECT LINKS
                    # =================================

                    if missing_platforms:

                        for platform in missing_platforms:

                            if platform in [

                                "instagram",

                                "facebook"
                            ]:

                                connect_url = (

                                    f"{settings.APP_BASE_URL}"
                                    f"/oauth/meta/connect"
                                    f"?whatsapp_number="
                                    f"{phone_number}"
                                )

                            elif platform == "linkedin":

                                connect_url = (

                                    f"{settings.APP_BASE_URL}"
                                    f"/oauth/linkedin/connect"
                                    f"?whatsapp_number="
                                    f"{phone_number}"
                                )

                            elif platform == "twitter":

                                connect_url = (

                                    f"{settings.APP_BASE_URL}"
                                    f"/oauth/twitter/connect"
                                    f"?whatsapp_number="
                                    f"{phone_number}"
                                )

                            else:

                                continue

                            print(
                                "CONNECT URL:"
                            )

                            print(
                                connect_url
                            )

                            await send_message(

                                phone_number,

                                (
                                    f"⚠️ Your "
                                    f"{platform.title()} "
                                    f"account is not connected.\n\n"

                                    f"Connect here:\n"

                                    f"{connect_url}"
                                )
                            )

                        return {
                            "success":
                            True
                        }

                    # =================================
                    # CREATE JOBS
                    # =================================
                    
                    jobs = (
                        
                        

                        post_service
                        .create_immediate_publish_jobs(

                            db=db,

                            whatsapp_number=
                            phone_number,

                            pending_post=
                            pending_post,

                            platforms=
                            selected_platforms
                        )
                    )
                    
                    

                    # jobs = (

                    #     post_service
                    #     .create_immediate_publish_jobs(

                    #         db=db,

                    #         whatsapp_number=
                    #         phone_number,

                    #         pending_post=
                    #         pending_post
                    #     )
                    # )

                    print("CREATED JOBS:")
                    print(jobs)

                    await send_message(

                        phone_number,

                        (
                            "🚀 Publishing "
                            "started..."
                        )
                    )

                    return {
                        "success":
                        True
                    }

                # =====================================
                # SCHEDULE POST
                # =====================================

                if (
                    button_id
                    == "schedule_post"
                ):

                    session_service.set_waiting_for_schedule(

                        phone_number,

                        True
                    )

                    await send_message(

                        phone_number,

                        (
                            "Send schedule time.\n\n"

                            "Examples:\n"

                            "- after 2 hours\n"

                            "- tomorrow 9am\n"

                            "- tonight 8pm"
                        )
                    )

                    return {
                        "success":
                        True
                    }

            # =========================================
            # TEXT MESSAGE
            # =========================================

            text = ""

            if (
                message.get("type")
                == "text"
            ):

                text = (

                    message["text"]
                    .get("body", "")
                )

            print("TEXT:")
            print(text)

            # =========================================
            # WAITING FOR SCHEDULE
            # =========================================

            waiting_for_schedule = (

                session_service
                .is_waiting_for_schedule(
                    phone_number
                )
            )

            if waiting_for_schedule:

                scheduled_time = (

                    scheduler_service
                    .parse_schedule_time(
                        text
                    )
                )

                if not scheduled_time:

                    await send_message(

                        phone_number,

                        (
                            "Invalid "
                            "schedule time"
                        )
                    )

                    return {
                        "success":
                        False
                    }

                pending_post = (

                    session_service
                    .get_pending_post(
                        phone_number
                    )
                )

                platforms = (

                    session_service
                    .get_selected_platforms(
                        phone_number
                    )
                )

                post_service.create_scheduled_publish_jobs(

                    db=db,

                    whatsapp_number=
                    phone_number,

                    pending_post=
                    pending_post,

                    platforms=
                    platforms,

                    scheduled_time=
                    scheduled_time
                )

                session_service.delete_pending_post(
                    phone_number
                )

                session_service.delete_selected_platforms(
                    phone_number
                )

                session_service.set_waiting_for_schedule(

                    phone_number,

                    False
                )

                await send_message(

                    phone_number,

                    (
                        f"✅ Post scheduled "
                        f"for {scheduled_time}"
                    )
                )

                return {
                    "success":
                    True
                }

            # =========================================
            # GENERATE AI POST
            # =========================================

            ai_post = await (
                post_service
                .create_ai_post(

                    db,

                    phone_number,

                    text
                )
            )

            print("AI POST:")
            print(ai_post)

            session_service.save_pending_post(

                phone_number,

                ai_post
            )

            await send_image(

                phone_number,

                ai_post["image_url"],

                ai_post["caption"]
            )

            await asyncio.sleep(2)

            await send_buttons(

                phone_number,

                "Choose platform",

                [

                    {
                        "id":
                        "platform_instagram",

                        "title":
                        "Instagram"
                    },

                    {
                        "id":
                        "platform_linkedin",

                        "title":
                        "LinkedIn"
                    },

                    {
                        "id":
                        "platform_twitter",

                        "title":
                        "Twitter"
                    }
                ]
            )

            return {
                "success":
                True
            }

        except Exception as e:

            print("================================")
            print("WEBHOOK ERROR")
            print("================================")

            print(str(e))

            traceback.print_exc()

            return {
                "success":
                False
            }