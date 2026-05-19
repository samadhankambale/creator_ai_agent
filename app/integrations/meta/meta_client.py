import requests
from app.core.config import settings


def exchange_code_for_token(code: str) -> dict:
    response = requests.get(
        "https://graph.facebook.com/v20.0/oauth/access_token",
        params={
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": settings.META_REDIRECT_URI,
            "code": code,
        },
        timeout=30,
    )
    data = response.json()
    print("META TOKEN RESPONSE:", data)
    return data


def get_facebook_pages(access_token: str) -> dict:
    response = requests.get(
        "https://graph.facebook.com/v20.0/me/accounts",
        params={"access_token": access_token},
        timeout=30,
    )
    return response.json()


def get_instagram_business_account(page_id: str, page_access_token: str) -> dict:
    response = requests.get(
        f"https://graph.facebook.com/v20.0/{page_id}",
        params={
            "fields": "instagram_business_account",
            "access_token": page_access_token,
        },
        timeout=30,
    )
    return response.json()