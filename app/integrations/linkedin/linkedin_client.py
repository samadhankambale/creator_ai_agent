import requests
from app.core.config import settings


# ──────────────────────────────────────────────────────────────
# OAUTH
# ──────────────────────────────────────────────────────────────

def get_linkedin_auth_url(whatsapp_number: str) -> str:
    """
    IMPORTANT: scope must include openid + profile + email
    so the /userinfo endpoint works. w_member_social alone
    gives 403 on profile fetch.
    """
    return (
        "https://www.linkedin.com/oauth/v2/authorization"
        f"?client_id={settings.LINKEDIN_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"
        "&scope=openid%20profile%20email%20w_member_social"
        f"&state={whatsapp_number}"
    )


def exchange_code_for_token(code: str) -> dict:
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        },
        timeout=30,
    )
    return response.json()


def get_linkedin_profile(access_token: str) -> dict:
    """
    Uses OpenID /userinfo endpoint.
    Returns: { sub, name, given_name, family_name, email, picture }
    Requires openid + profile scopes — NOT the old /v2/me endpoint.
    """
    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=30,
    )
    data = response.json()
    print("LINKEDIN USERINFO:", data)
    return data


# ──────────────────────────────────────────────────────────────
# PUBLISHING
# ──────────────────────────────────────────────────────────────

def _upload_image(access_token: str, person_urn: str, image_url: str) -> str | None:
    """
    Upload image to LinkedIn media and return asset URN.
    Steps: register upload → PUT bytes → return asset URN.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Step 1: Register upload
    register_resp = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers=headers,
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": person_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        },
        timeout=30,
    )
    register_data = register_resp.json()
    print("LINKEDIN REGISTER UPLOAD:", register_data)

    if "value" not in register_data:
        print("LINKEDIN REGISTER FAILED:", register_data)
        return None

    upload_url = (
        register_data["value"]
        ["uploadMechanism"]
        ["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]
        ["uploadUrl"]
    )
    asset_urn = register_data["value"]["asset"]

    # Step 2: Download image from Pollinations and PUT to LinkedIn
    image_bytes = requests.get(image_url, timeout=60).content
    put_resp = requests.put(
        upload_url,
        data=image_bytes,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    print("LINKEDIN IMAGE PUT STATUS:", put_resp.status_code)

    if put_resp.status_code not in (200, 201):
        return None

    return asset_urn


def post_to_linkedin(
    access_token: str,
    person_id: str,
    caption: str,
    image_url: str,
) -> dict:
    """
    Post image + caption to LinkedIn via ugcPosts API.
    Falls back to text-only if image upload fails.
    """
    person_urn = f"urn:li:person:{person_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    print("=" * 40)
    print("LINKEDIN POST: uploading image")
    print("PERSON URN:", person_urn)
    print("=" * 40)

    asset_urn = _upload_image(access_token, person_urn, image_url)

    if asset_urn:
        post_body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": caption[:200]},
                            "media": asset_urn,
                            "title": {"text": "Post"},
                        }
                    ],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
    else:
        print("LINKEDIN: image upload failed, falling back to text only")
        post_body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

    print("LINKEDIN POST BODY:", post_body)

    response = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers=headers,
        json=post_body,
        timeout=30,
    )

    print("LINKEDIN POST STATUS:", response.status_code)
    print("LINKEDIN POST RESPONSE:", response.text)

    if response.status_code in (200, 201):
        return {
            "success": True,
            "platform": "linkedin",
            "post_id": response.headers.get("x-restli-id", ""),
        }

    return {
        "success": False,
        "error": "LinkedIn post failed",
        "details": response.text,
        "status_code": response.status_code,
    }