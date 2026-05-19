from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import requests as http_requests

from app.core.config import settings
from app.database.dependencies import get_db
from app.integrations.meta.meta_client import (
    exchange_code_for_token,
    get_facebook_pages,
    get_instagram_business_account,
)
from app.integrations.whatsapp.whatsapp_client import send_message_sync, send_buttons_sync
from app.services.social_account_service import social_account_service

router = APIRouter(tags=["Meta OAuth"])


# ──────────────────────────────────────────────────────────────
# INSTAGRAM CONNECT
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/meta/connect")
async def connect_instagram(whatsapp_number: str):
    oauth_url = (
        "https://www.facebook.com/v20.0/dialog/oauth"
        f"?client_id={settings.META_APP_ID}"
        f"&redirect_uri={settings.META_REDIRECT_URI}"
        "&scope=instagram_basic,instagram_content_publish,pages_show_list"
        f"&state={whatsapp_number}|instagram"
    )
    print("INSTAGRAM AUTH URL:", oauth_url)
    return RedirectResponse(url=oauth_url)


# ──────────────────────────────────────────────────────────────
# THREADS CONNECT — uses THREADS_APP_ID (different from META)
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/threads/connect")
async def connect_threads(whatsapp_number: str):
    oauth_url = (
        "https://threads.net/oauth/authorize"
        f"?client_id={settings.THREADS_APP_ID}"
        f"&redirect_uri={settings.THREADS_REDIRECT_URI}"
        "&scope=threads_basic,threads_content_publish"
        "&response_type=code"
        f"&state={whatsapp_number}|threads"
    )
    print("THREADS AUTH URL:", oauth_url)
    return RedirectResponse(url=oauth_url)


# ──────────────────────────────────────────────────────────────
# INSTAGRAM CALLBACK
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/meta/callback")
async def meta_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    code = request.query_params.get("code")
    state = request.query_params.get("state", "")
    error = request.query_params.get("error")

    whatsapp_number = state.split("|")[0] if state else None

    print("=" * 40)
    print("META CALLBACK")
    print("CODE:", code)
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("=" * 40)

    if error:
        return HTMLResponse(
            content=_html_page("Authorization Failed", error),
            status_code=400,
        )

    if not code:
        return HTMLResponse(
            content=_html_page("Authorization Failed", "No authorization code received."),
            status_code=400,
        )

    if not whatsapp_number:
        return HTMLResponse(
            content=_html_page(
                "Authorization Failed",
                "Missing WhatsApp number. Please try connecting again from WhatsApp.",
            ),
            status_code=400,
        )

    try:
        token_data = exchange_code_for_token(code)
        access_token = token_data.get("access_token")

        if not access_token:
            return HTMLResponse(
                content=_html_page("Token Exchange Failed", str(token_data)),
                status_code=400,
            )

        pages_data = get_facebook_pages(access_token)
        pages = pages_data.get("data", [])

        if not pages:
            return HTMLResponse(
                content=_html_page(
                    "No Facebook Pages Found",
                    "Please create a Facebook page linked to your Instagram Business account.",
                ),
                status_code=400,
            )

        ig_user_id = None
        page_access_token = None

        for page in pages:
            ig_data = get_instagram_business_account(page["id"], page["access_token"])
            ig_business = ig_data.get("instagram_business_account")
            if ig_business:
                ig_user_id = ig_business["id"]
                page_access_token = page["access_token"]
                break

        if not ig_user_id:
            return HTMLResponse(
                content=_html_page(
                    "Instagram Business Account Not Found",
                    "Make sure your Instagram is a Business/Creator account linked to a Facebook page.",
                ),
                status_code=400,
            )

        social_account_service.connect_platform_account(
            db=db,
            whatsapp_number=whatsapp_number,
            platform="instagram",
            access_token=page_access_token,
            platform_user_id=ig_user_id,
            username="instagram_user",
        )

        print("INSTAGRAM CONNECTED:", ig_user_id, "for", whatsapp_number)

        send_message_sync(whatsapp_number, "✅ Instagram connected successfully!")
        send_buttons_sync(
            whatsapp_number,
            "Choose action",
            [
                {"id": "post_now", "title": "Post Now"},
                {"id": "schedule_post", "title": "Schedule"},
            ],
        )

        return HTMLResponse(
            content=_html_page(
                "✅ Instagram Connected!",
                "You can close this tab and return to WhatsApp.",
            ),
            status_code=200,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=_html_page("Connection Failed", str(e)),
            status_code=500,
        )


# ──────────────────────────────────────────────────────────────
# THREADS CALLBACK
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/threads/callback")
async def threads_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    code = request.query_params.get("code")
    state = request.query_params.get("state", "")
    error = request.query_params.get("error")

    whatsapp_number = state.split("|")[0] if state else None

    print("=" * 40)
    print("THREADS CALLBACK")
    print("CODE:", code)
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("=" * 40)

    if error:
        return HTMLResponse(
            content=_html_page("Authorization Failed", error),
            status_code=400,
        )

    if not code or not whatsapp_number:
        return HTMLResponse(
            content=_html_page("Authorization Failed", "Missing code or WhatsApp number."),
            status_code=400,
        )

    try:
        # Exchange code using THREADS_APP_ID + THREADS_APP_SECRET
        token_resp = http_requests.post(
            "https://graph.threads.net/oauth/access_token",
            data={
                "client_id": settings.THREADS_APP_ID,
                "client_secret": settings.THREADS_APP_SECRET,
                "redirect_uri": settings.THREADS_REDIRECT_URI,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        token_data = token_resp.json()
        print("THREADS TOKEN:", token_data)

        access_token = token_data.get("access_token")
        threads_user_id = str(token_data.get("user_id", ""))

        if not access_token or not threads_user_id:
            return HTMLResponse(
                content=_html_page("Token Exchange Failed", str(token_data)),
                status_code=400,
            )

        social_account_service.connect_platform_account(
            db=db,
            whatsapp_number=whatsapp_number,
            platform="threads",
            access_token=access_token,
            platform_user_id=threads_user_id,
            username="threads_user",
        )

        print("THREADS CONNECTED:", threads_user_id, "for", whatsapp_number)

        send_message_sync(whatsapp_number, "✅ Threads connected successfully!")
        send_buttons_sync(
            whatsapp_number,
            "Choose action",
            [
                {"id": "post_now", "title": "Post Now"},
                {"id": "schedule_post", "title": "Schedule"},
            ],
        )

        return HTMLResponse(
            content=_html_page(
                "✅ Threads Connected!",
                "You can close this tab and return to WhatsApp.",
            ),
            status_code=200,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=_html_page("Connection Failed", str(e)),
            status_code=500,
        )


def _html_page(title: str, message: str) -> str:
    return f"""
    <html>
      <head><title>{title}</title></head>
      <body style="font-family:Arial;text-align:center;padding-top:80px;max-width:500px;margin:auto">
        <h2>{title}</h2>
        <p>{message}</p>
      </body>
    </html>
    """