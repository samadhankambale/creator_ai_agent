import requests


# =====================================================
# GET LINKEDIN USER PROFILE
# =====================================================

async def get_linkedin_profile(
    access_token: str
):

    url = (
        "https://api.linkedin.com/v2/userinfo"
    )

    headers = {

        "Authorization": (
            f"Bearer {access_token}"
        )
    }

    response = requests.get(
        url,
        headers=headers
    )

    data = response.json()

    print("LINKEDIN PROFILE:")
    print(data)

    return data


# =====================================================
# CREATE LINKEDIN POST
# =====================================================

async def post_to_linkedin(
    caption,
    image_url,
    access_token,
    linkedin_user_id
):

    # ---------------------------------------------
    # STEP 1 — CREATE POST
    # ---------------------------------------------

    url = (
        "https://api.linkedin.com/v2/ugcPosts"
    )

    headers = {

        "Authorization": (
            f"Bearer {access_token}"
        ),

        "X-Restli-Protocol-Version": (
            "2.0.0"
        ),

        "Content-Type": (
            "application/json"
        )
    }


# import httpx

# async def post_to_linkedin(
#     caption,
#     image_url,
#     access_token,
#     user_urn
# ):

#     url = (
#         "https://api.linkedin.com/v2/"
#         "ugcPosts"
#     )

#     headers = {
#         "Authorization":
#         f"Bearer {access_token}",

#         "Content-Type":
#         "application/json"
#     }

#     payload = {
#         "author": user_urn,

#         "lifecycleState": "PUBLISHED",

#         "specificContent": {
#             "com.linkedin.ugc.ShareContent": {
#                 "shareCommentary": {
#                     "text": caption
#                 },

#                 "shareMediaCategory":
#                 "IMAGE",

#                 "media": [
#                     {
#                         "status": "READY",
#                         "originalUrl":
#                         image_url
#                     }
#                 ]
#             }
#         },

#         "visibility": {
#             "com.linkedin.ugc."
#             "MemberNetworkVisibility":
#             "PUBLIC"
#         }
#     }

#     async with httpx.AsyncClient(
#         timeout=60.0
#     ) as client:

#         response = await client.post(
#             url,
#             headers=headers,
#             json=payload
#         )

#     return response.json()