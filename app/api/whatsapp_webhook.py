from fastapi import APIRouter
from fastapi import Request

from fastapi.responses import (
    PlainTextResponse
)

from app.core.config import settings

from app.services.post_service import (
    create_post
)

from app.services.publishing_service import (
    publish_service
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message,
    send_platform_buttons
)

from app.integrations.instagram.instagram_client import (
    post_to_instagram
)

from app.integrations.linkedin.linkedin_client import (
    post_to_linkedin
)

router = APIRouter()


# ===================================================
# VERIFY WEBHOOK
# ===================================================

@router.get("/webhook")
async def verify_webhook(request: Request):

    mode = request.query_params.get(
        "hub.mode"
    )

    token = request.query_params.get(
        "hub.verify_token"
    )

    challenge = request.query_params.get(
        "hub.challenge"
    )

    print("MODE:", mode)
    print("TOKEN:", token)

    print(
        "ENV TOKEN:",
        settings.WHATSAPP_VERIFY_TOKEN
    )

    if (
        mode == "subscribe"
        and token ==
        settings.WHATSAPP_VERIFY_TOKEN
    ):

        return PlainTextResponse(
            content=challenge
        )

    return PlainTextResponse(
        content="Verification failed",
        status_code=403
    )


# ===================================================
# RECEIVE WHATSAPP MESSAGE
# ===================================================

@router.post("/webhook")
async def receive_message(payload: dict):

    try:

        print("FULL WEBHOOK PAYLOAD:")
        print(payload)

        value = (
            payload["entry"][0]
            ["changes"][0]
            ["value"]
        )

        print("VALUE:")
        print(value)

        # ---------------------------------------------------
        # IGNORE STATUS EVENTS
        # ---------------------------------------------------

        if "messages" not in value:

            print("NO MESSAGES FOUND")

            return {
                "success": True,
                "message": "No messages"
            }

        message = value["messages"][0]

        print("FULL MESSAGE:")
        print(message)

        message_type = message.get(
            "type"
        )

        print("MESSAGE TYPE:")
        print(message_type)

        phone_number = message["from"]

        print("PHONE NUMBER:")
        print(phone_number)

        # ===================================================
        # INTERACTIVE BUTTON FLOW
        # ===================================================

        if message_type == "interactive":

            print("INTERACTIVE BUTTON FLOW")

            button_reply = (
                message["interactive"]
                ["button_reply"]
                ["id"]
            )

            print("BUTTON CLICKED:")
            print(button_reply)

            pending_post = (
                await publish_service
                .get_pending_post(
                    phone_number
                )
            )

            print("PENDING POST:")
            print(pending_post)

            if not pending_post:

                await send_message(
                    phone_number,
                    "No pending post found."
                )

                return {"success": False}

            social_accounts = (
                await publish_service
                .get_social_accounts(
                    phone_number
                )
            )

            print("SOCIAL ACCOUNTS:")
            print(social_accounts)

            # ---------------------------------------------
            # INSTAGRAM
            # ---------------------------------------------

            if button_reply == "instagram":

                print("POSTING TO INSTAGRAM")

                instagram_account = next(
                    (
                        account
                        for account
                        in social_accounts
                        if account["platform"]
                        == "instagram"
                    ),
                    None
                )

                print("INSTAGRAM ACCOUNT:")
                print(instagram_account)

                if not instagram_account:

                    await send_message(
                        phone_number,
                        "Instagram account not connected."
                    )

                    return {"success": False}

                result = await post_to_instagram(

                    pending_post["image_url"],

                    pending_post["caption"],

                    instagram_account[
                        "access_token"
                    ],

                    instagram_account[
                        "platform_user_id"
                    ]
                )

                print("INSTAGRAM RESULT:")
                print(result)

                await send_message(
                    phone_number,
                    "✅ Posted on Instagram"
                )

                return {"success": True}

            # ---------------------------------------------
            # LINKEDIN
            # ---------------------------------------------

            if button_reply == "linkedin":

                print("POSTING TO LINKEDIN")

                linkedin_account = next(
                    (
                        account
                        for account
                        in social_accounts
                        if account["platform"]
                        == "linkedin"
                    ),
                    None
                )

                print("LINKEDIN ACCOUNT:")
                print(linkedin_account)

                if not linkedin_account:

                    await send_message(
                        phone_number,
                        "LinkedIn account not connected."
                    )

                    return {"success": False}

                result = await post_to_linkedin(

                    pending_post["caption"],

                    pending_post["image_url"],

                    linkedin_account[
                        "access_token"
                    ],

                    linkedin_account[
                        "platform_user_id"
                    ]
                )

                print("LINKEDIN RESULT:")
                print(result)

                await send_message(
                    phone_number,
                    "✅ Posted on LinkedIn"
                )

                return {"success": True}

            # ---------------------------------------------
            # BOTH
            # ---------------------------------------------

            if button_reply == "both":

                print("POSTING TO BOTH")

                for account in social_accounts:

                    print("ACCOUNT:")
                    print(account)

                    # -------------------------------------
                    # INSTAGRAM
                    # -------------------------------------

                    if (
                        account["platform"]
                        == "instagram"
                    ):

                        await post_to_instagram(

                            pending_post["image_url"],

                            pending_post["caption"],

                            account["access_token"],

                            account[
                                "platform_user_id"
                            ]
                        )

                    # -------------------------------------
                    # LINKEDIN
                    # -------------------------------------

                    if (
                        account["platform"]
                        == "linkedin"
                    ):

                        await post_to_linkedin(

                            pending_post["caption"],

                            pending_post["image_url"],

                            account["access_token"],

                            account[
                                "platform_user_id"
                            ]
                        )

                await send_message(
                    phone_number,
                    "✅ Posted on all platforms"
                )

                return {"success": True}

        # ===================================================
        # NORMAL TEXT FLOW
        # ===================================================

        if message_type == "text":

            print("TEXT MESSAGE FLOW")

            text = (
                message["text"]["body"]
            )

            print("TEXT:")
            print(text)

            # ---------------------------------------------
            # CREATE AI POST
            # ---------------------------------------------

            result = await create_post(
                text
            )

            print("AI RESULT:")
            print(result)

            # ---------------------------------------------
            # LOAD CONNECTED SOCIAL ACCOUNTS
            # ---------------------------------------------

            social_accounts = (
                await publish_service
                .get_social_accounts(
                    phone_number
                )
            )

            print("FOUND SOCIAL ACCOUNTS:")
            print(social_accounts)

            # ---------------------------------------------
            # SAVE PENDING POST
            # ---------------------------------------------

            await publish_service.create_pending_post(

                phone_number,

                result["caption"],

                result["image_url"],

                social_accounts
            )

            print("PENDING POST SAVED")

            # ---------------------------------------------
            # SEND BUTTONS
            # ---------------------------------------------

            await send_platform_buttons(

                phone_number,

                result["caption"]
            )

            print("BUTTONS SENT")

            return {"success": True}

        return {
            "success": False,
            "message":
            "Unsupported message type"
        }

    except Exception as e:

        print("WEBHOOK ERROR:")
        print(str(e))

        return {
            "success": False,
            "error": str(e)
        }