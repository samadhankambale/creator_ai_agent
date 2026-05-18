import requests

from app.core.config import (
    settings
)


# =====================================================
# WHATSAPP API URL
# =====================================================

WHATSAPP_API_URL = (

    f"https://graph.facebook.com/v22.0/"
    f"{settings.WHATSAPP_PHONE_NUMBER_ID}"
    f"/messages"
)


# =====================================================
# HEADERS
# =====================================================

HEADERS = {

    "Authorization":
    f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",

    "Content-Type":
    "application/json"
}


# =====================================================
# SEND MESSAGE
# =====================================================

async def send_message(
    to,
    text
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
            text
        }
    }

    response = requests.post(

        WHATSAPP_API_URL,

        json=payload,

        headers=HEADERS
    )

    response_json = (
        response.json()
    )

    print("SEND MESSAGE RESPONSE:")
    print(response_json)

    return response_json


# =====================================================
# SEND MESSAGE SYNC
# =====================================================

def send_message_sync(
    to,
    text
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
            text
        }
    }

    response = requests.post(

        WHATSAPP_API_URL,

        json=payload,

        headers=HEADERS
    )

    response_json = (
        response.json()
    )

    print("SYNC MESSAGE RESPONSE:")
    print(response_json)

    return response_json


# =====================================================
# SEND IMAGE
# =====================================================

async def send_image(
    to,
    image_url,
    caption=None
):

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
            caption or ""
        }
    }

    response = requests.post(

        WHATSAPP_API_URL,

        json=payload,

        headers=HEADERS
    )

    response_json = (
        response.json()
    )

    print("SEND IMAGE RESPONSE:")
    print(response_json)

    return response_json


# =====================================================
# SEND BUTTONS
# =====================================================

async def send_buttons(
    to,
    body_text,
    buttons
):

    button_components = []

    for button in buttons:

        button_components.append(

            {
                "type":
                "reply",

                "reply": {

                    "id":
                    button["id"],

                    "title":
                    button["title"]
                }
            }
        )

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
                button_components
            }
        }
    }

    response = requests.post(

        WHATSAPP_API_URL,

        json=payload,

        headers=HEADERS
    )

    response_json = (
        response.json()
    )

    print("BUTTON RESPONSE:")
    print(response_json)

    return response_json


# =====================================================
# SEND BUTTONS SYNC
# =====================================================

def send_buttons_sync(
    to,
    body_text,
    buttons
):

    button_components = []

    for button in buttons:

        button_components.append(

            {
                "type":
                "reply",

                "reply": {

                    "id":
                    button["id"],

                    "title":
                    button["title"]
                }
            }
        )

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
                button_components
            }
        }
    }

    response = requests.post(

        WHATSAPP_API_URL,

        json=payload,

        headers=HEADERS
    )

    response_json = (
        response.json()
    )

    print("SYNC BUTTON RESPONSE:")
    print(response_json)

    return response_json