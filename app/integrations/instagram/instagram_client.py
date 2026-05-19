import requests

GRAPH_URL = "https://graph.facebook.com/v20.0"


def post_to_instagram(
    access_token: str,
    platform_user_id: str,   # matches publishing_service.publish() call
    image_url: str,
    caption: str,
    ig_user_id: str = None,  # alias for backward compat
) -> dict:
    """
    Two-step Instagram publish:
    1. Create media container
    2. Publish the container
    """

    # support both parameter names
    user_id = platform_user_id or ig_user_id

    print("=" * 40)
    print("INSTAGRAM: creating media container")
    print("IG USER ID:", user_id)
    print("IMAGE URL:", image_url)
    print("=" * 40)

    # ── Step 1: create container ──────────────────────
    container_resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    container_data = container_resp.json()
    print("CONTAINER RESPONSE:", container_data)

    if "id" not in container_data:
        return {
            "success": False,
            "error": "Media container creation failed",
            "details": container_data,
        }

    creation_id = container_data["id"]

    # ── Step 2: publish ───────────────────────────────
    publish_resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish_data = publish_resp.json()
    print("PUBLISH RESPONSE:", publish_data)

    if "id" not in publish_data:
        return {
            "success": False,
            "error": "Media publish failed",
            "details": publish_data,
        }

    return {
        "success": True,
        "platform": "instagram",
        "post_id": publish_data["id"],
    }