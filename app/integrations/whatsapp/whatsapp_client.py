import requests

from app.core.config import settings


WHATSAPP_URL = (

    "https://graph.facebook.com"

    f"/v20.0/"

    f"{settings.WHATSAPP_PHONE_NUMBER_ID}"

    "/messages"
)


HEADERS = {

    "Authorization":
    f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",

    "Content-Type":
    "application/json"
}


# ======================================================
# SEND TEXT MESSAGE
# ======================================================

async def send_message(
    to: str,
    message: str
):

    payload = {

        "messaging_product":
        "whatsapp",

        "to":
        to,

        "type":
        "text",

        "text": {

            "body":
            message[:4096]
        }
    }

    response = requests.post(

        WHATSAPP_URL,

        headers=HEADERS,

        json=payload
    )

    print("SEND MESSAGE RESPONSE:")

    print(response.json())

    return response.json()


# ======================================================
# SEND IMAGE
# ======================================================

async def send_image(
    to: str,
    image_url: str,
    caption: str = ""
):

    # ----------------------------------------------
    # WHATSAPP CAPTION LIMIT
    # ----------------------------------------------

    caption = caption[:1024]

    payload = {

        "messaging_product":
        "whatsapp",

        "to":
        to,

        "type":
        "image",

        "image": {

            "link":
            image_url,

            "caption":
            caption
        }
    }

    response = requests.post(

        WHATSAPP_URL,

        headers=HEADERS,

        json=payload
    )

    print("SEND IMAGE RESPONSE:")

    print(response.json())

    return response.json()


# ======================================================
# SEND BUTTONS
# ======================================================

async def send_buttons(
    to: str,
    body_text: str,
    buttons: list
):

    # ----------------------------------------------
    # WHATSAPP LIMIT
    # ----------------------------------------------

    body_text = body_text[:1024]

    formatted_buttons = []

    for button in buttons:

        formatted_buttons.append({

            "type": "reply",

            "reply": {

                "id":
                button["id"],

                "title":
                button["title"][:20]
            }
        })

    payload = {

        "messaging_product":
        "whatsapp",

        "to":
        to,

        "type":
        "interactive",

        "interactive": {

            "type":
            "button",

            "body": {

                "text":
                body_text
            },

            "action": {

                "buttons":
                formatted_buttons
            }
        }
    }

    response = requests.post(

        WHATSAPP_URL,

        headers=HEADERS,

        json=payload
    )

    print("BUTTON RESPONSE:")

    print(response.json())

    return response.json()


# ======================================================
# SEND LIST MESSAGE
# ======================================================

async def send_list_message(
    to: str,
    body_text: str,
    button_text: str,
    sections: list
):

    payload = {

        "messaging_product":
        "whatsapp",

        "to":
        to,

        "type":
        "interactive",

        "interactive": {

            "type":
            "list",

            "body": {

                "text":
                body_text[:1024]
            },

            "action": {

                "button":
                button_text[:20],

                "sections":
                sections
            }
        }
    }

    response = requests.post(

        WHATSAPP_URL,

        headers=HEADERS,

        json=payload
    )

    print("LIST RESPONSE:")

    print(response.json())

    return response.json()


# ======================================================
# SEND TEMPLATE
# ======================================================

async def send_template_message(
    to: str,
    template_name: str,
    language_code: str = "en_US"
):

    payload = {

        "messaging_product":
        "whatsapp",

        "to":
        to,

        "type":
        "template",

        "template": {

            "name":
            template_name,

            "language": {

                "code":
                language_code
            }
        }
    }

    response = requests.post(

        WHATSAPP_URL,

        headers=HEADERS,

        json=payload
    )

    print("TEMPLATE RESPONSE:")

    print(response.json())

    return response.json()