from fastapi import APIRouter
from fastapi import Request

from app.core.config import settings

from app.services.meta_service import (
    exchange_code_for_token
)

from app.services.publishing_service import (
    publish_service
)

router = APIRouter()


# ---------------------------------------------------
# CONNECT META
# ---------------------------------------------------

@router.get("/oauth/meta/connect")
async def connect_meta():

    oauth_url = (
        "https://www.facebook.com/v20.0/dialog/oauth"
        f"?client_id={settings.META_APP_ID}"
        f"&redirect_uri={settings.META_REDIRECT_URI}"
        "&scope=instagram_basic,"
        "instagram_content_publish,"
        "pages_show_list"
    )

    return {
        "oauth_url": oauth_url
    }


# ---------------------------------------------------
# CONNECT LINKEDIN
# ---------------------------------------------------

@router.get("/oauth/linkedin/connect")
async def connect_linkedin():

    oauth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?client_id={settings.LINKEDIN_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
        "&scope=w_member_social"
    )

    return {
        "oauth_url": oauth_url
    }


# ---------------------------------------------------
# META CALLBACK
# ---------------------------------------------------

@router.get("/oauth/meta/callback")
async def meta_callback(
    request: Request
):

    code = request.query_params.get(
        "code"
    )

    if not code:

        return {
            "error":
            "No code received from Meta"
        }

    token_data = exchange_code_for_token(
        code
    )

    print("TOKEN DATA:")
    print(token_data)

    access_token = token_data.get(
        "access_token"
    )

    instagram_user_id = token_data.get(
        "instagram_user_id"
    )

    # ---------------------------------------------
    # SAVE SOCIAL ACCOUNT
    # ---------------------------------------------

    await publish_service.save_social_account(
        phone_number="917448101276",
        platform="instagram",
        access_token=access_token,
        platform_user_id=instagram_user_id
    )

    print("INSTAGRAM ACCOUNT SAVED")

    return {
        "message":
        "Meta connected successfully",

        "token_data":
        token_data
    }


# ---------------------------------------------------
# LINKEDIN CALLBACK
# ---------------------------------------------------

@router.get("/oauth/linkedin/callback")
async def linkedin_callback(
    request: Request
):

    code = request.query_params.get(
        "code"
    )

    if not code:

        return {
            "error":
            "No code received from LinkedIn"
        }

    return {
        "message":
        "LinkedIn OAuth successful",

        "code": code
    }