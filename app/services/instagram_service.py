import requests

GRAPH_URL = "https://graph.facebook.com/v20.0"


# STEP 1: Create media container
def create_media(ig_user_id: str, access_token: str, image_url: str, caption: str):
    url = f"{GRAPH_URL}/{ig_user_id}/media"

    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token
    }

    response = requests.post(url, data=payload)
    return response.json()


# STEP 2: Publish media
def publish_media(ig_user_id: str, access_token: str, creation_id: str):
    url = f"{GRAPH_URL}/{ig_user_id}/media_publish"

    payload = {
        "creation_id": creation_id,
        "access_token": access_token
    }

    response = requests.post(url, data=payload)
    return response.json()


# MAIN FUNCTION (optional but recommended)
def post_to_instagram(ig_user_id: str, access_token: str, image_url: str, caption: str):
    media = create_media(ig_user_id, access_token, image_url, caption)

    if "id" not in media:
        return {
            "error": "Media creation failed",
            "details": media
        }

    creation_id = media["id"]

    result = publish_media(ig_user_id, access_token, creation_id)

    return {
        "message": "Post published successfully",
        "result": result
    }