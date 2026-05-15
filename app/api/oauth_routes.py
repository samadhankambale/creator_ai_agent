import requests

from fastapi import (
    APIRouter,
    Request,
    Depends
)

from fastapi.responses import RedirectResponse

from app.integrations.whatsapp.whatsapp_client import (
    send_message,
    send_buttons
)

from sqlalchemy.orm import Session

from app.core.config import settings

from app.database.dependencies import (
    get_db
)

from app.integrations.linkedin.linkedin_client import (
    get_linkedin_profile
)

from app.services.social_account_service import (
    social_account_service
)

from app.services.meta_service import (
    exchange_code_for_token,
    get_instagram_business_account
)


router = APIRouter()


# =====================================================
# META CONNECT
# =====================================================

@router.get("/oauth/meta/connect")
async def connect_meta(
    whatsapp_number: str
):

    oauth_url = (

        "https://www.facebook.com/v20.0/dialog/oauth"

        f"?client_id={settings.META_APP_ID}"

        f"&redirect_uri={settings.META_REDIRECT_URI}"

        "&scope=instagram_basic,"
        "instagram_content_publish,"
        "pages_show_list"

        f"&state={whatsapp_number}"
    )

    return RedirectResponse(
        oauth_url
    )


# =====================================================
# LINKEDIN CONNECT
# =====================================================

@router.get("/oauth/linkedin/connect")
async def connect_linkedin(
    whatsapp_number: str
):

    oauth_url = (

        "https://www.linkedin.com/oauth/v2/authorization"

        f"?client_id={settings.LINKEDIN_CLIENT_ID}"

        "&response_type=code"

        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"

        "&scope="

        "openid%20"

        "profile%20"

        "email%20"

        "w_member_social"

        f"&state={whatsapp_number}"
    )

    return {

        "oauth_url": oauth_url
    }
    
    
# =====================================================
# META CALLBACK
# =====================================================

@router.get("/oauth/meta/callback")
async def meta_callback(
    request: Request,
    db: Session = Depends(get_db)
):

    try:

        # ----------------------------------------------
        # GET CODE
        # ----------------------------------------------

        code = request.query_params.get(
            "code"
        )

        whatsapp_number = request.query_params.get(
            "state"
        )

        if not code:

            return {
                "error": "No code received"
            }

        # ----------------------------------------------
        # EXCHANGE TOKEN
        # ----------------------------------------------

        token_data = exchange_code_for_token(
            code
        )

        print("META TOKEN RESPONSE:")
        print(token_data)

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:

            return {
                "error":
                "Could not get access token"
            }

        # ----------------------------------------------
        # GET FACEBOOK PAGES
        # ----------------------------------------------

        pages_response = requests.get(

            "https://graph.facebook.com/v20.0/me/accounts",

            params={
                "access_token":
                access_token
            }
        )

        pages_data = pages_response.json()

        print("PAGES DATA:")
        print(pages_data)

        pages = pages_data.get(
            "data",
            []
        )

        if not pages:

            return {
                "error":
                "No Facebook pages found"
            }

        page = pages[0]

        page_id = page["id"]

        page_access_token = page[
            "access_token"
        ]

        # ----------------------------------------------
        # GET INSTAGRAM BUSINESS ACCOUNT
        # ----------------------------------------------

        instagram_response = requests.get(

            f"https://graph.facebook.com/v20.0/{page_id}",

            params={

                "fields":
                "instagram_business_account",

                "access_token":
                page_access_token
            }
        )

        instagram_data = (
            instagram_response.json()
        )

        print("INSTAGRAM DATA:")
        print(instagram_data)

        instagram_business = (
            instagram_data.get(
                "instagram_business_account"
            )
        )

        if not instagram_business:

            return {
                "error":
                "Instagram Business Account not found"
            }

        instagram_user_id = (
            instagram_business["id"]
        )

        # ----------------------------------------------
        # SAVE ACCOUNT
        # ----------------------------------------------

        social_account_service.connect_platform_account(

            db=db,

            whatsapp_number=
            whatsapp_number,

            platform="instagram",

            access_token=
            page_access_token,

            platform_user_id=
            instagram_user_id,

            username="instagram_user"
        )

        # ----------------------------------------------
        # SEND WHATSAPP SUCCESS MESSAGE
        # ----------------------------------------------

        await send_message(

            whatsapp_number,

            (
                "✅ Instagram connected successfully.\n\n"
                "Now choose what you want to do."
            )
        )

        # ----------------------------------------------
        # SEND ACTION BUTTONS
        # ----------------------------------------------

        await send_buttons(

            whatsapp_number,

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

        # ----------------------------------------------
        # RETURN SUCCESS PAGE
        # ----------------------------------------------

        return {

            "success": True,

            "message":
            "Instagram connected successfully. Return to WhatsApp."
        }

    except Exception as e:

        print("META CALLBACK ERROR:")
        print(str(e))

        return {
            "success": False,
            "error": str(e)
        }

# =====================================================
# LINKEDIN CALLBACK
# =====================================================

@router.get("/oauth/linkedin/callback")
async def linkedin_callback(
    request: Request,
    db: Session = Depends(get_db)
):

    code = request.query_params.get(
        "code"
    )

    if not code:

        return {
            "error": (
                "No code received"
            )
        }

    # -------------------------------------------------
    # EXCHANGE TOKEN
    # -------------------------------------------------

    token_url = (
        "https://www.linkedin.com/oauth/v2/accessToken"
    )

    payload = {

        "grant_type":
        "authorization_code",

        "code":
        code,

        "redirect_uri":
        settings.LINKEDIN_REDIRECT_URI,

        "client_id":
        settings.LINKEDIN_CLIENT_ID,

        "client_secret":
        settings.LINKEDIN_CLIENT_SECRET
    }

    token_response = requests.post(
        token_url,
        data=payload
    )

    token_data = token_response.json()

    print("LINKEDIN TOKEN:")
    print(token_data)

    access_token = token_data.get(
        "access_token"
    )

    if not access_token:

        return {

            "error":
            "Could not get LinkedIn token",

            "details":
            token_data
        }

    # -------------------------------------------------
    # GET PROFILE
    # -------------------------------------------------

    profile = await get_linkedin_profile(
        access_token
    )

    linkedin_user_id = profile.get(
        "sub"
    )

    full_name = profile.get(
        "name"
    )

    # -------------------------------------------------
    # TEMP USER
    # -------------------------------------------------

    # later replace using OAuth state
    
    
    whatsapp_number = request.query_params.get("state")

    # whatsapp_number = "917448101276"

    # -------------------------------------------------
    # SAVE ACCOUNT
    # -------------------------------------------------

    social_account_service.connect_platform_account(

        db=db,

        whatsapp_number=
        whatsapp_number,

        platform="linkedin",

        access_token=
        access_token,

        platform_user_id=
        linkedin_user_id,

        username=full_name
    )

    return {

        "success": True,

        "message": (
            "LinkedIn connected successfully"
        ),

        "profile": profile
    }