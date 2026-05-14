from fastapi import APIRouter
from app.services.instagram_service import create_media, publish_media

router = APIRouter()


@router.post("/instagram/post")
async def post_instagram(data: dict):
    ig_user_id = data["ig_user_id"]
    access_token = data["access_token"]
    image_url = data["image_url"]
    caption = data["caption"]

    media = create_media(ig_user_id, access_token, image_url, caption)

    if "id" not in media:
        return {"error": media}

    creation_id = media["id"]

    result = publish_media(ig_user_id, access_token, creation_id)

    return {
        "message": "Posted successfully",
        "result": result
    }