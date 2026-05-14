import requests

from app.core.config import settings


def exchange_code_for_token(
    code: str
):

    # ---------------------------------------------
    # GET ACCESS TOKEN
    # ---------------------------------------------

    token_url = (
        "https://graph.facebook.com/v20.0/oauth/access_token"
    )

    token_response = requests.get(
        token_url,
        params={

            "client_id":
            settings.META_APP_ID,

            "client_secret":
            settings.META_APP_SECRET,

            "redirect_uri":
            settings.META_REDIRECT_URI,

            "code":
            code
        }
    )

    token_data = token_response.json()

    print("TOKEN RESPONSE:")
    print(token_data)

    access_token = token_data.get(
        "access_token"
    )

    # ---------------------------------------------
    # GET FACEBOOK PAGES
    # ---------------------------------------------

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

    page_id = pages[0]["id"]

    # ---------------------------------------------
    # GET INSTAGRAM BUSINESS ACCOUNT
    # ---------------------------------------------

    instagram_response = requests.get(

        f"https://graph.facebook.com/v20.0/"
        f"{page_id}",

        params={
            "fields":
            "instagram_business_account",

            "access_token":
            access_token
        }
    )

    instagram_data = (
        instagram_response.json()
    )

    print("INSTAGRAM DATA:")
    print(instagram_data)

    instagram_business_account = (
        instagram_data.get(
            "instagram_business_account",
            {}
        )
    )

    instagram_user_id = (
        instagram_business_account.get(
            "id"
        )
    )

    return {

        "access_token":
        access_token,

        "instagram_user_id":
        instagram_user_id
    }