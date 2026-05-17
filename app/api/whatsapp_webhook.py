import traceback

from fastapi import (
    APIRouter,
    Request,
    Depends
)

from sqlalchemy.orm import Session

from app.database.dependencies import (
    get_db
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message,
    send_image,
    send_buttons
)

from app.services.post_service import (
    post_service
)

from app.services.session_service import (
    session_service
)

from app.workers.scheduled_post_worker import (
    process_publish_job
)

from app.utils.datetime_parser import (
    parse_schedule_datetime
)


router = APIRouter()


# =====================================================
# VERIFY WEBHOOK
# =====================================================

@router.get("/webhook")
async def verify_webhook(
    request: Request
):

    mode = request.query_params.get(
        "hub.mode"
    )

    challenge = request.query_params.get(
        "hub.challenge"
    )

    if mode == "subscribe":

        return int(challenge)

    return {
        "error": "Verification failed"
    }


# =====================================================
# RECEIVE MESSAGE
# =====================================================

@router.post("/webhook")
async def receive_message(
    payload: dict,
    db: Session = Depends(get_db)
):

    try:

        print("================================")
        print("WEBHOOK HIT")
        print("================================")

        print(payload)

        value = (
            payload["entry"][0]
            ["changes"][0]
            ["value"]
        )

        if "messages" not in value:

            print("NO MESSAGE FOUND")

            return {
                "success": True
            }

        message = value[
            "messages"
        ][0]

        message_type = message.get(
            "type"
        )

        phone_number = message[
            "from"
        ]

        print("PHONE NUMBER:")
        print(phone_number)

        print("MESSAGE TYPE:")
        print(message_type)

        # =================================================
        # INTERACTIVE BUTTONS
        # =================================================

        if message_type == "interactive":

            interactive = message.get(
                "interactive",
                {}
            )

            button_reply = None

            # ---------------------------------------------
            # BUTTON REPLY
            # ---------------------------------------------

            if "button_reply" in interactive:

                button_reply = (

                    interactive
                    ["button_reply"]
                    ["id"]
                )

            # ---------------------------------------------
            # LIST REPLY
            # ---------------------------------------------

            elif "list_reply" in interactive:

                button_reply = (

                    interactive
                    ["list_reply"]
                    ["id"]
                )

            print("BUTTON REPLY:")
            print(button_reply)

            if not button_reply:

                return {
                    "success": False
                }

            # =============================================
            # PLATFORM SELECTION
            # =============================================

            if (
                button_reply
                .startswith("platform_")
            ):

                selected = (
                    button_reply
                    .replace(
                        "platform_",
                        ""
                    )
                )

                platforms = []

                if selected == "all":

                    platforms = [

                        "instagram",

                        "linkedin",

                        "twitter",

                        "facebook"
                    ]

                else:

                    platforms = [selected]

                print("SELECTED PLATFORMS:")
                print(platforms)

                session_service.save_selected_platforms(

                    phone_number,

                    platforms
                )

                # -----------------------------------------
                # SHOW ACTION BUTTONS
                # -----------------------------------------

                await send_buttons(

                    phone_number,

                    "Choose action",

                    [
                        {
                            "id":
                            "action_post_now",

                            "title":
                            "Post Now"
                        },
                        {
                            "id":
                            "action_schedule",

                            "title":
                            "Schedule"
                        }
                    ]
                )

                return {
                    "success": True
                }

            # =============================================
            # POST NOW
            # =============================================

            if button_reply == "action_post_now":

                pending_post = (
                    session_service
                    .get_pending_post(
                        phone_number
                    )
                )

                if not pending_post:

                    await send_message(

                        phone_number,

                        "No pending post found."
                    )

                    return {
                        "success": False
                    }

                platforms = (
                    session_service
                    .get_selected_platforms(
                        phone_number
                    )
                )

                print("PENDING POST:")
                print(pending_post)

                print("PLATFORMS:")
                print(platforms)

                if not platforms:

                    await send_message(

                        phone_number,

                        "Please select platform first."
                    )

                    return {
                        "success": False
                    }

                # -----------------------------------------
                # CHECK MISSING CONNECTIONS
                # -----------------------------------------

                missing = (
                    post_service
                    .get_missing_platforms(

                        db,

                        phone_number,

                        platforms
                    )
                )

                print("MISSING:")
                print(missing)

                if missing:

                    connect_message = (
                        "Connect your accounts:\n\n"
                    )

                    for platform in missing:

                        # -----------------------------
                        # INSTAGRAM
                        # -----------------------------

                        if platform == "instagram":

                            connect_message += (

                                "Instagram:\n"
                                
                                f"https://aware-ambition-obvious.ngrok-free.dev/oauth/meta/connect"

                                # f"https://YOUR_NGROK/oauth/meta/connect"

                                f"?whatsapp_number={phone_number}\n\n"
                            )

                        # -----------------------------
                        # LINKEDIN
                        # -----------------------------

                        elif platform == "linkedin":

                            connect_message += (

                                "LinkedIn:\n"
                                f"https://aware-ambition-obvious.ngrok-free.dev/oauth/meta/connect"

                                # f"https://YOUR_NGROK/oauth/linkedin/connect"

                                f"?whatsapp_number={phone_number}\n\n"
                            )

                        # -----------------------------
                        # TWITTER
                        # -----------------------------

                        elif platform == "twitter":

                            connect_message += (
                                "Twitter support coming soon.\n\n"
                            )

                        # -----------------------------
                        # FACEBOOK
                        # -----------------------------

                        elif platform == "facebook":

                            connect_message += (
                                "Facebook support coming soon.\n\n"
                            )

                    await send_message(

                        phone_number,

                        connect_message
                    )

                    return {
                        "success": False
                    }

                # -----------------------------------------
                # CREATE PUBLISH JOBS
                # -----------------------------------------

                jobs = (
                    post_service
                    .create_immediate_publish_jobs(

                        db=db,

                        whatsapp_number=
                        phone_number,

                        post_id=
                        pending_post[
                            "post_id"
                        ],

                        platforms=
                        platforms
                    )
                )

                print("CREATED JOBS:")
                print(jobs)

                # -----------------------------------------
                # START CELERY TASKS
                # -----------------------------------------

                for job in jobs:

                    process_publish_job.delay(
                        job.id
                    )

                await send_message(

                    phone_number,

                    "✅ Publishing started"
                )

                # -----------------------------------------
                # CLEAR SESSION
                # -----------------------------------------

                session_service.delete_pending_post(
                    phone_number
                )

                session_service.delete_selected_platforms(
                    phone_number
                )

                return {
                    "success": True
                }

            # =============================================
            # SCHEDULE FLOW
            # =============================================

            if button_reply == "action_schedule":

                session_service.enable_schedule_mode(
                    phone_number
                )

                await send_message(

                    phone_number,

                    (
                        "Send schedule time.\n\n"
                        "Examples:\n"
                        "Tomorrow 9 PM\n"
                        "After 2 hours\n"
                        "Monday 8 AM"
                    )
                )

                return {
                    "success": True
                }

        # =================================================
        # TEXT MESSAGE
        # =================================================

        if message_type == "text":

            text = (
                message["text"]
                ["body"]
            )

            print("TEXT:")
            print(text)

            # =============================================
            # SCHEDULE TIME INPUT
            # =============================================

            if (
                session_service
                .is_schedule_mode(
                    phone_number
                )
            ):

                scheduled_time = (
                    parse_schedule_datetime(
                        text
                    )
                )

                print("SCHEDULED TIME:")
                print(scheduled_time)

                if not scheduled_time:

                    await send_message(

                        phone_number,

                        (
                            "Could not understand time.\n"
                            "Try again."
                        )
                    )

                    return {
                        "success": False
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

                jobs = (
                    post_service
                    .create_scheduled_publish_jobs(

                        db=db,

                        whatsapp_number=
                        phone_number,

                        post_id=
                        pending_post[
                            "post_id"
                        ],

                        platforms=
                        platforms,

                        scheduled_time=
                        scheduled_time
                    )
                )

                print("SCHEDULED JOBS:")
                print(jobs)

                await send_message(

                    phone_number,

                    (
                        f"✅ Post scheduled for:\n"
                        f"{scheduled_time}"
                    )
                )

                # -----------------------------------------
                # CLEAR SESSION
                # -----------------------------------------

                session_service.disable_schedule_mode(
                    phone_number
                )

                session_service.delete_pending_post(
                    phone_number
                )

                session_service.delete_selected_platforms(
                    phone_number
                )

                return {
                    "success": True
                }

            # =============================================
            # GENERATE AI POST
            # =============================================

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

            # ---------------------------------------------
            # SAVE SESSION
            # ---------------------------------------------

            session_service.save_pending_post(

                phone_number,

                ai_post
            )

            # ---------------------------------------------
            # SEND IMAGE PREVIEW
            # ---------------------------------------------

            await send_image(

                phone_number,

                ai_post[
                    "image_url"
                ],

                ai_post[
                    "caption"
                ]
            )

            # ---------------------------------------------
            # SHOW PLATFORM BUTTONS
            # ---------------------------------------------

            await send_buttons(

                phone_number,

                "Choose platforms",

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
                "success": True
            }

        return {
            "success": True
        }

    except Exception as e:

        print("WEBHOOK ERROR:")
        print(str(e))

        traceback.print_exc()

        return {
            "success": False,
            "error": str(e)
        }