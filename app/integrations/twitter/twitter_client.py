import requests
import secrets
import hashlib
import base64
from app.core.config import settings


# ──────────────────────────────────────────────────────────────
# PKCE HELPERS
# ──────────────────────────────────────────────────────────────

def generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ──────────────────────────────────────────────────────────────
# OAUTH
# ──────────────────────────────────────────────────────────────

def get_twitter_auth_url(whatsapp_number: str, code_verifier: str) -> str:
    code_challenge = generate_code_challenge(code_verifier)
    return (
        "https://twitter.com/i/oauth2/authorize"
        f"?client_id={settings.TWITTER_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={settings.TWITTER_REDIRECT_URI}"
        "&scope=tweet.read%20tweet.write%20users.read%20offline.access"
        f"&state={whatsapp_number}"
        f"&code_challenge={code_challenge}"
        "&code_challenge_method=S256"
    )


def exchange_code_for_token(code: str, code_verifier: str) -> dict:
    response = requests.post(
        "https://api.twitter.com/2/oauth2/token",
        auth=(settings.TWITTER_CLIENT_ID, settings.TWITTER_CLIENT_SECRET),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.TWITTER_REDIRECT_URI,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    data = response.json()
    print("TWITTER TOKEN RESPONSE:", data)
    return data


def get_twitter_user(access_token: str) -> dict:
    response = requests.get(
        "https://api.twitter.com/2/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = response.json()
    print("TWITTER USER:", data)
    return data


# ──────────────────────────────────────────────────────────────
# PUBLISHING
# ──────────────────────────────────────────────────────────────

def _upload_image(access_token: str, image_url: str) -> str | None:
    """
    Download image from URL and upload to Twitter media upload endpoint.
    Returns media_id string or None if upload fails.
    Twitter v1.1 media upload requires OAuth 1.0a — but with OAuth 2.0
    we use the v2 endpoint which supports direct URL attachment via
    card_uri. Instead we download and upload via chunked upload.
    """
    try:
        # Download image bytes
        img_resp = requests.get(image_url, timeout=60)
        if img_resp.status_code != 200:
            print("TWITTER: failed to download image")
            return None

        image_bytes = img_resp.content

        # Upload to Twitter media endpoint
        upload_resp = requests.post(
            "https://upload.twitter.com/1.1/media/upload.json",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"media": image_bytes},
            timeout=60,
        )
        upload_data = upload_resp.json()
        print("TWITTER MEDIA UPLOAD:", upload_data)

        return str(upload_data.get("media_id_string", ""))

    except Exception as e:
        print(f"TWITTER IMAGE UPLOAD ERROR: {e}")
        return None


def post_to_twitter(
    access_token: str,
    twitter_user_id: str,
    caption: str,
    image_url: str,
) -> dict:
    """
    Post tweet with image to Twitter/X using v2 API.
    Falls back to text-only if image upload fails.
    """

    print("=" * 40)
    print("TWITTER: posting tweet")
    print("USER ID:", twitter_user_id)
    print("=" * 40)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Try uploading image first
    media_id = _upload_image(access_token, image_url)

    # Build tweet payload
    if media_id:
        payload = {
            "text": caption,
            "media": {"media_ids": [media_id]},
        }
    else:
        print("TWITTER: image upload failed, posting text only")
        payload = {"text": caption}

    response = requests.post(
        "https://api.twitter.com/2/tweets",
        headers=headers,
        json=payload,
        timeout=30,
    )

    print("TWITTER POST STATUS:", response.status_code)
    print("TWITTER POST RESPONSE:", response.text)

    if response.status_code in (200, 201):
        data = response.json()
        return {
            "success": True,
            "platform": "twitter",
            "post_id": data.get("data", {}).get("id", ""),
        }

    return {
        "success": False,
        "error": "Twitter post failed",
        "details": response.text,
        "status_code": response.status_code,
    }