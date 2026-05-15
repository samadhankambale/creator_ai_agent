from fastapi import (
    APIRouter,
    Request,
    Depends
)
import traceback 
from sqlalchemy.orm import Session

from app.database.dependencies import (
    get_db
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message,
    send_image,
    send_buttons,
    send_list_message
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


@router.get("/webhook")
async def verify_webhook(
    request: Request
):

    mode = request.query_params.get(
        "hub.mode"
    )

    token = request.query_params.get(
        "hub.verify_token"
    )

    challenge = request.query_params.get(
        "hub.challenge"
    )

    if mode == "subscribe":
        return int(challenge)

    return {
        "error": "Verification failed"
    }


@router.post("/webhook")
async def receive_message(
    payload: dict,
    db: Session = Depends(get_db)
):

    try:

        value = (
            payload["entry"][0]
            ["changes"][0]
            ["value"]
        )

        if "messages" not in value:

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

        # ==================================================
        # INTERACTIVE FLOW
        # ==================================================

        if message_type == "interactive":

            interactive = message.get(
                "interactive",
                {}
            )

            button_reply = None

            # ----------------------------------------------
            # BUTTON REPLY
            # ----------------------------------------------

            if "button_reply" in interactive:

                button_reply = (
                    interactive
                    ["button_reply"]
                    ["id"]
                )

            # ----------------------------------------------
            # LIST REPLY
            # ----------------------------------------------

            elif "list_reply" in interactive:

                button_reply = (
                    interactive
                    ["list_reply"]
                    ["id"]
                )

            # ----------------------------------------------
            # INVALID
            # ----------------------------------------------

            if not button_reply:

                print("NO BUTTON REPLY FOUND")

                return {
                    "success": False
                }

            # ----------------------------------------------
            # PLATFORM SELECTION
            # ----------------------------------------------

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

                session_service.save_selected_platforms(
                    phone_number,
                    platforms
                )

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

            # ----------------------------------------------
            # POST NOW
            # ----------------------------------------------

            if button_reply == "action_post_now":

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

                missing = (
                    post_service
                    .get_missing_platforms(
                        db,
                        phone_number,
                        platforms
                    )
                )

                if missing:

                    msg = (
                        "Connect accounts first:\n\n"
                    )

                    for platform in missing:

                        if platform == "instagram":

                            msg += (
                                f"Instagram:\n"
                                f"https://aware-ambition-obvious.ngrok-free.dev/oauth/meta/connect?whatsapp_number={phone_number}\n\n"
                            )

                        elif platform == "linkedin":

                            msg += (
                                f"LinkedIn:\n"
                                f"https://aware-ambition-obvious.ngrok-free.dev/oauth/linkedin/connect?whatsapp_number={phone_number}\n\n"
                            )

                        elif platform == "twitter":

                            msg += (
                                "Twitter Coming Soon\n\n"
                            )

                        elif platform == "facebook":

                            msg += (
                                "Facebook Coming Soon\n\n"
                            )

                    await send_message(
                        phone_number,
                        msg
                    )

                    return {
                        "success": False
                    }

                jobs = (
                    post_service
                    .create_immediate_publish_jobs(
                        db=db,
                        whatsapp_number=phone_number,
                        post_id=pending_post["post_id"],
                        platforms=platforms
                    )
                )

                for job in jobs:

                    process_publish_job.delay(
                        job.id
                    )

                await send_message(
                    phone_number,
                    "✅ Publishing started"
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

            # ----------------------------------------------
            # SCHEDULE
            # ----------------------------------------------

            if button_reply == "action_schedule":

                session_service.enable_schedule_mode(
                    phone_number
                )

                await send_message(
                    phone_number,
                    (
                        "Send schedule time.\n\n"
                        "Example:\n"
                        "Tomorrow 9 PM"
                    )
                )

                return {
                    "success": True
                }

        # ==================================================
        # TEXT MESSAGE
        # ==================================================

        if message_type == "text":

            text = (
                message["text"]
                ["body"]
            )

            # ----------------------------------------------
            # SCHEDULE TIME
            # ----------------------------------------------

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

                if not scheduled_time:

                    await send_message(
                        phone_number,
                        "Could not understand time."
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
                        whatsapp_number=phone_number,
                        post_id=pending_post["post_id"],
                        platforms=platforms,
                        scheduled_time=scheduled_time
                    )
                )

                session_service.disable_schedule_mode(
                    phone_number
                )

                session_service.delete_pending_post(
                    phone_number
                )

                session_service.delete_selected_platforms(
                    phone_number
                )

                await send_message(
                    phone_number,
                    (
                        f"✅ Scheduled successfully for:\n"
                        f"{scheduled_time}"
                    )
                )

                return {
                    "success": True
                }

            # ----------------------------------------------
            # GENERATE AI POST
            # ----------------------------------------------

            ai_post = await (
                post_service
                .create_ai_post(
                    db,
                    phone_number,
                    text
                )
            )

            session_service.save_pending_post(
                phone_number,
                ai_post
            )

            await send_image(
                phone_number,
                ai_post["image_url"],
                ai_post["caption"]
            )

            await send_list_message(

                phone_number,

                "Choose platforms",

                "Platforms",

                [
                    {
                        "title":
                        "Social Platforms",

                        "rows": [

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
                            },

                            {
                                "id":
                                "platform_facebook",

                                "title":
                                "Facebook"
                            },

                            {
                                "id":
                                "platform_all",

                                "title":
                                "All Platforms"
                            }
                        ]
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
        
        
    
            
        
        

    # except Exception as e:

    #     print("WEBHOOK ERROR:")
    #     print(str(e))

    #     return {
    #         "success": False
    #     }