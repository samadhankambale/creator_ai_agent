import os
import tempfile
import requests

from app.core.config import (
    settings
)


# =====================================================
# AUTH URL
# =====================================================

def get_linkedin_auth_url(
    whatsapp_number
):

    scope = (
        "w_member_social"
    )

    url = (

        "https://www.linkedin.com/oauth/v2/authorization"

        f"?response_type=code"

        f"&client_id={settings.LINKEDIN_CLIENT_ID}"

        f"&redirect_uri={settings.LINKEDIN_REDIRECT_URI}"

        f"&scope={scope}"

        f"&state={whatsapp_number}"
    )

    return url


# =====================================================
# EXCHANGE TOKEN
# =====================================================

def exchange_code_for_token(
    code
):

    url = (
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

    response = requests.post(

        url,

        data=payload
    )

    return response.json()


# =====================================================
# GET MEMBER PROFILE
# =====================================================

def get_linkedin_profile(
    access_token
):

    url = (
        "https://api.linkedin.com/v2/me"
    )

    headers = {

        "Authorization":
        f"Bearer {access_token}"
    }

    response = requests.get(

        url,

        headers=headers
    )

    profile = response.json()

    print("LINKEDIN PROFILE:")
    print(profile)

    return profile


# =====================================================
# DOWNLOAD IMAGE
# =====================================================

def download_image(
    image_url
):

    response = requests.get(
        image_url
    )

    temp_file = tempfile.NamedTemporaryFile(

        delete=False,

        suffix=".jpg"
    )

    temp_file.write(
        response.content
    )

    temp_file.close()

    return temp_file.name


# =====================================================
# REGISTER IMAGE UPLOAD
# =====================================================

def register_image_upload(
    access_token,
    member_urn
):

    url = (
        "https://api.linkedin.com/v2/assets?action=registerUpload"
    )

    headers = {

        "Authorization":
        f"Bearer {access_token}",

        "Content-Type":
        "application/json"
    }

    payload = {

        "registerUploadRequest": {

            "recipes": [

                "urn:li:digitalmediaRecipe:feedshare-image"
            ],

            "owner":
            member_urn,

            "serviceRelationships": [

                {

                    "relationshipType":
                    "OWNER",

                    "identifier":
                    "urn:li:userGeneratedContent"
                }
            ]
        }
    }

    response = requests.post(

        url,

        headers=headers,

        json=payload
    )

    return response.json()


# =====================================================
# UPLOAD IMAGE
# =====================================================

def upload_image_binary(
    upload_url,
    image_path
):

    with open(
        image_path,
        "rb"
    ) as image_file:

        headers = {

            "Content-Type":
            "image/jpeg"
        }

        response = requests.put(

            upload_url,

            headers=headers,

            data=image_file
        )

    return response.status_code


# =====================================================
# CREATE POST
# =====================================================

def create_linkedin_post(
    access_token,
    member_urn,
    caption,
    asset
):

    url = (
        "https://api.linkedin.com/v2/ugcPosts"
    )

    headers = {

        "Authorization":
        f"Bearer {access_token}",

        "X-Restli-Protocol-Version":
        "2.0.0",

        "Content-Type":
        "application/json"
    }

    payload = {

        "author":
        member_urn,

        "lifecycleState":
        "PUBLISHED",

        "specificContent": {

            "com.linkedin.ugc.ShareContent": {

                "shareCommentary": {

                    "text":
                    caption
                },

                "shareMediaCategory":
                "IMAGE",

                "media": [

                    {

                        "status":
                        "READY",

                        "description": {

                            "text":
                            caption
                        },

                        "media":
                        asset,

                        "title": {

                            "text":
                            "AI Generated Post"
                        }
                    }
                ]
            }
        },

        "visibility": {

            "com.linkedin.ugc.MemberNetworkVisibility":
            "PUBLIC"
        }
    }

    response = requests.post(

        url,

        headers=headers,

        json=payload
    )

    return response.json()


# =====================================================
# MAIN PUBLISH
# =====================================================

def post_to_linkedin(
    access_token,
    member_id,
    caption,
    image_url
):

    try:

        print("================================")
        print("LINKEDIN PUBLISH START")
        print("================================")

        member_urn = (
            f"urn:li:person:{member_id}"
        )

        print("MEMBER URN:")
        print(member_urn)

        # ============================================
        # DOWNLOAD IMAGE
        # ============================================

        image_path = download_image(
            image_url
        )

        # ============================================
        # REGISTER UPLOAD
        # ============================================

        register_response = (
            register_image_upload(

                access_token,

                member_urn
            )
        )

        print("REGISTER RESPONSE:")
        print(register_response)

        upload_data = (

            register_response[
                "value"
            ][
                "uploadMechanism"
            ][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]
        )

        upload_url = (
            upload_data[
                "uploadUrl"
            ]
        )

        asset = (
            register_response[
                "value"
            ][
                "asset"
            ]
        )

        # ============================================
        # UPLOAD IMAGE
        # ============================================

        upload_status = (
            upload_image_binary(

                upload_url,

                image_path
            )
        )

        print("UPLOAD STATUS:")
        print(upload_status)

        # ============================================
        # CREATE POST
        # ============================================

        post_response = (
            create_linkedin_post(

                access_token,

                member_urn,

                caption,

                asset
            )
        )

        print("POST RESPONSE:")
        print(post_response)

        if os.path.exists(
            image_path
        ):

            os.remove(
                image_path
            )

        if (
            "id"
            in post_response
        ):

            return {

                "success":
                True,

                "response":
                post_response
            }

        return {

            "success":
            False,

            "response":
            post_response
        }

    except Exception as e:

        print("LINKEDIN ERROR:")
        print(str(e))

        return {

            "success":
            False,

            "error":
            str(e)
        }