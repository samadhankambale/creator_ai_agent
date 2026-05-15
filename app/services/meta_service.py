import requests

from app.core.config import settings


# ======================================================
# EXCHANGE CODE FOR ACCESS TOKEN
# ======================================================

def exchange_code_for_token(
    code: str
):

    url = (
        "https://graph.facebook.com/v20.0/oauth/access_token"
    )

    params = {

        "client_id":
        settings.META_APP_ID,

        "client_secret":
        settings.META_APP_SECRET,

        "redirect_uri":
        settings.META_REDIRECT_URI,

        "code":
        code
    }

    response = requests.get(

        url,

        params=params
    )

    data = response.json()

    print("META TOKEN RESPONSE:")
    print(data)

    return data


# ======================================================
# GET FACEBOOK PAGES
# ======================================================

def get_facebook_pages(
    access_token: str
):

    url = (
        "https://graph.facebook.com/v20.0/me/accounts"
    )

    response = requests.get(

        url,

        params={
            "access_token":
            access_token
        }
    )

    data = response.json()

    print("FACEBOOK PAGES:")
    print(data)

    return data


# ======================================================
# GET INSTAGRAM BUSINESS ACCOUNT
# ======================================================

def get_instagram_business_account(
    page_id: str,
    access_token: str
):

    url = (
        f"https://graph.facebook.com/v20.0/{page_id}"
    )

    params = {

        "fields":
        "instagram_business_account",

        "access_token":
        access_token
    }

    response = requests.get(

        url,

        params=params
    )

    data = response.json()

    print("INSTAGRAM BUSINESS ACCOUNT:")
    print(data)

    return data