from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.dependencies import get_db
from app.integrations.linkedin.linkedin_client import (
    get_linkedin_auth_url,
    exchange_code_for_token,
    get_linkedin_profile,
)
from app.integrations.whatsapp.whatsapp_client import send_message_sync, send_buttons_sync
from app.services.social_account_service import social_account_service
from app.services.post_connect_service import on_platform_connected

router = APIRouter(prefix="/oauth/linkedin", tags=["LinkedIn OAuth"])


# ──────────────────────────────────────────────────────────────
# CONNECT
# ──────────────────────────────────────────────────────────────

@router.get("/connect")
async def connect_linkedin(whatsapp_number: str):
    auth_url = get_linkedin_auth_url(whatsapp_number)
    print("LINKEDIN AUTH URL:", auth_url)
    return RedirectResponse(url=auth_url)


# ──────────────────────────────────────────────────────────────
# CALLBACK
# ──────────────────────────────────────────────────────────────

@router.get("/callback")
async def linkedin_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db),
):
    whatsapp_number = state

    print("=" * 40)
    print("LINKEDIN CALLBACK")
    print("CODE:", code)
    print("STATE / WHATSAPP:", whatsapp_number)
    print("ERROR:", error)
    print("=" * 40)

    if error:
        return HTMLResponse(
            content=_html_page("LinkedIn Authorization Failed", f"{error}: {error_description}"),
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
        # ── Exchange code for token ───────────────────
        token_data = exchange_code_for_token(code)
        print("LINKEDIN TOKEN DATA:", token_data)

        access_token = token_data.get("access_token")
        if not access_token:
            return HTMLResponse(
                content=_html_page("Token Exchange Failed", str(token_data)),
                status_code=400,
            )

        # ── Get profile via OpenID userinfo ───────────
        # Requires openid + profile scopes
        profile = get_linkedin_profile(access_token)
        print("LINKEDIN PROFILE:", profile)

        # /userinfo returns 'sub' as the unique user ID
        person_id = profile.get("sub")
        username = profile.get("name") or profile.get("given_name", "LinkedIn User")

        if not person_id:
            return HTMLResponse(
                content=_html_page(
                    "Profile Fetch Failed",
                    f"Could not get LinkedIn profile. Response: {profile}",
                ),
                status_code=400,
            )

        # ── Save to DB ────────────────────────────────
        from app.services.user_service import user_service
        user = user_service.get_or_create(db, whatsapp_number)
        social_account_service.upsert(
            db=db,
            user_id=user.id,
            platform="linkedin",
            access_token=access_token,
            platform_user_id=person_id,
            username=username,
        )

        print("LINKEDIN CONNECTED:", person_id, "for", whatsapp_number)

        # ── Notify user ───────────────────────────────
        on_platform_connected(db=db, whatsapp_number=whatsapp_number, platform="linkedin")

        return HTMLResponse(
            content=_html_page(
                "✅ LinkedIn Connected!",
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