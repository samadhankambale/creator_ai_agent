from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import requests as http_requests
import redis

from app.core.config import settings
from app.database.dependencies import get_db
from app.integrations.meta.meta_client import (
    exchange_code_for_token,
    get_facebook_pages,
    get_instagram_business_account,
)
from app.integrations.twitter.twitter_client import (
    get_twitter_auth_url,
    exchange_code_for_token as twitter_exchange_code,
    get_twitter_user,
    generate_code_verifier,
)
from app.integrations.whatsapp.whatsapp_client import send_message_sync, send_buttons_sync
from app.services.social_account_service import social_account_service
from app.services.post_connect_service import on_platform_connected

router = APIRouter(tags=["OAuth"])

# Redis for storing PKCE code_verifier temporarily
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


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
# THREADS CONNECT
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
# TWITTER CONNECT
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/twitter/connect")
async def connect_twitter(whatsapp_number: str):
    # Generate PKCE verifier and store in Redis for 10 minutes
    code_verifier = generate_code_verifier()
    redis_client.setex(f"twitter_pkce:{whatsapp_number}", 600, code_verifier)

    auth_url = get_twitter_auth_url(whatsapp_number, code_verifier)
    print("TWITTER AUTH URL:", auth_url)
    return RedirectResponse(url=auth_url)


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
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("=" * 40)

    if error:
        return HTMLResponse(content=_html_page("Authorization Failed", error), status_code=400)

    if not code or not whatsapp_number:
        return HTMLResponse(
            content=_html_page("Authorization Failed", "Missing code or WhatsApp number."),
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

        from app.services.user_service import user_service
        user = user_service.get_or_create(db, whatsapp_number)
        social_account_service.upsert(
            db=db,
            user_id=user.id,
            platform="instagram",
            access_token=page_access_token,
            platform_user_id=ig_user_id,
            username=ig_user_id,
        )

        print("INSTAGRAM CONNECTED:", ig_user_id)

        on_platform_connected(db=db, whatsapp_number=whatsapp_number, platform="instagram")

        return HTMLResponse(
            content=_html_page("✅ Instagram Connected!", "You can close this tab and return to WhatsApp."),
            status_code=200,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=_html_page("Connection Failed", str(e)), status_code=500)


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
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("=" * 40)

    if error:
        return HTMLResponse(content=_html_page("Authorization Failed", error), status_code=400)

    if not code or not whatsapp_number:
        return HTMLResponse(
            content=_html_page("Authorization Failed", "Missing code or WhatsApp number."),
            status_code=400,
        )

    try:
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

        from app.services.user_service import user_service
        user = user_service.get_or_create(db, whatsapp_number)
        social_account_service.upsert(
            db=db,
            user_id=user.id,
            platform="threads",
            access_token=access_token,
            platform_user_id=threads_user_id,
            username=threads_user_id,
        )

        print("THREADS CONNECTED:", threads_user_id)

        on_platform_connected(db=db, whatsapp_number=whatsapp_number, platform="threads")

        return HTMLResponse(
            content=_html_page("✅ Threads Connected!", "You can close this tab and return to WhatsApp."),
            status_code=200,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=_html_page("Connection Failed", str(e)), status_code=500)


# ──────────────────────────────────────────────────────────────
# TWITTER CALLBACK
# ──────────────────────────────────────────────────────────────

@router.get("/oauth/twitter/callback")
async def twitter_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    code = request.query_params.get("code")
    state = request.query_params.get("state", "")
    error = request.query_params.get("error")

    whatsapp_number = state if state else None

    print("=" * 40)
    print("TWITTER CALLBACK")
    print("WHATSAPP NUMBER:", whatsapp_number)
    print("=" * 40)

    if error:
        return HTMLResponse(content=_html_page("Authorization Failed", error), status_code=400)

    if not code or not whatsapp_number:
        return HTMLResponse(
            content=_html_page("Authorization Failed", "Missing code or WhatsApp number."),
            status_code=400,
        )

    try:
        # Retrieve PKCE verifier from Redis
        code_verifier = redis_client.get(f"twitter_pkce:{whatsapp_number}")
        if not code_verifier:
            return HTMLResponse(
                content=_html_page(
                    "Session Expired",
                    "OAuth session expired. Please try connecting again from WhatsApp.",
                ),
                status_code=400,
            )

        # Exchange code for token
        token_data = twitter_exchange_code(code, code_verifier)
        access_token = token_data.get("access_token")

        if not access_token:
            return HTMLResponse(
                content=_html_page("Token Exchange Failed", str(token_data)),
                status_code=400,
            )

        # Get Twitter user info
        user_data = get_twitter_user(access_token)
        twitter_user_id = user_data.get("data", {}).get("id", "")
        username = user_data.get("data", {}).get("username", "twitter_user")

        if not twitter_user_id:
            return HTMLResponse(
                content=_html_page("Profile Fetch Failed", str(user_data)),
                status_code=400,
            )

        # Clean up PKCE verifier from Redis
        redis_client.delete(f"twitter_pkce:{whatsapp_number}")

        from app.services.user_service import user_service
        user = user_service.get_or_create(db, whatsapp_number)
        social_account_service.upsert(
            db=db,
            user_id=user.id,
            platform="twitter",
            access_token=access_token,
            platform_user_id=twitter_user_id,
            username=username,
        )

        print("TWITTER CONNECTED:", twitter_user_id, username)

        on_platform_connected(db=db, whatsapp_number=whatsapp_number, platform="twitter")

        return HTMLResponse(
            content=_html_page("✅ Twitter Connected!", f"@{username} connected. You can close this tab and return to WhatsApp."),
            status_code=200,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=_html_page("Connection Failed", str(e)), status_code=500)


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