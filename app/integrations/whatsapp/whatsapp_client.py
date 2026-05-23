import httpx
import requests
from app.core.config import settings


def _base_url() -> str:
    return (
        f"https://graph.facebook.com/v20.0"
        f"/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


def _headers() -> dict:
    """Read token fresh every call so token refresh works without restart."""
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────────────────────
# ASYNC (FastAPI routes)
# ──────────────────────────────────────────────────────────────

async def send_message(to: str, text: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_base_url(), headers=_headers(), json=payload)
    print("WA send_message:", resp.status_code)
    return resp.json()


async def send_buttons(to: str, body_text: str, buttons: list) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_base_url(), headers=_headers(), json=payload)
    print("WA send_buttons:", resp.status_code)
    return resp.json()


async def send_image(to: str, image_url: str, caption: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_base_url(), headers=_headers(), json=payload)
    print("WA send_image:", resp.status_code)
    return resp.json()


# ──────────────────────────────────────────────────────────────
# SYNC (Celery workers)
# ──────────────────────────────────────────────────────────────

def send_message_sync(to: str, text: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    resp = requests.post(_base_url(), headers=_headers(), json=payload, timeout=30)
    print("WA send_message_sync:", resp.status_code)
    return resp.json()


def send_buttons_sync(to: str, body_text: str, buttons: list) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons
                ]
            },
        },
    }
    resp = requests.post(_base_url(), headers=_headers(), json=payload, timeout=30)
    print("WA send_buttons_sync:", resp.status_code)
    return resp.json()