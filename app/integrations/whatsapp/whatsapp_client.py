import httpx

from app.core.config import settings


# ---------------------------------------------------
# SEND NORMAL TEXT MESSAGE
# ---------------------------------------------------

async def send_message(
    phone_number: str,
    text: str
):

    url = (
        "https://graph.facebook.com/v20.0/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
        "/messages"
    )

    headers = {
        "Authorization":
        f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",

        "Content-Type":
        "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",

        "to": phone_number,

        "type": "text",

        "text": {
            "body": text
        }
    }

    async with httpx.AsyncClient() as client:

        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

        print("SEND MESSAGE RESPONSE:")
        print(response.json())


# ---------------------------------------------------
# SEND PLATFORM BUTTONS
# ---------------------------------------------------

async def send_platform_buttons(
    phone_number: str,
    caption: str
):

    url = (
        "https://graph.facebook.com/v20.0/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
        "/messages"
    )

    headers = {
        "Authorization":
        f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",

        "Content-Type":
        "application/json"
    }

    # ---------------------------------------------
    # SHORTEN CAPTION
    # ---------------------------------------------

    short_caption = caption[:300]

    body_text = (
        f"📌 {short_caption}\n\n"
        "Where do you want to post?"
    )

    payload = {
        "messaging_product": "whatsapp",

        "to": phone_number,

        "type": "interactive",

        "interactive": {

            "type": "button",

            "body": {
                "text": body_text
            },

            "action": {

                "buttons": [

                    {
                        "type": "reply",

                        "reply": {
                            "id": "instagram",
                            "title": "Instagram"
                        }
                    },

                    {
                        "type": "reply",

                        "reply": {
                            "id": "linkedin",
                            "title": "LinkedIn"
                        }
                    },

                    {
                        "type": "reply",

                        "reply": {
                            "id": "both",
                            "title": "Both"
                        }
                    }
                ]
            }
        }
    }

    async with httpx.AsyncClient() as client:

        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

        print("BUTTON RESPONSE:")
        print(response.json())