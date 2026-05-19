import requests


def post_to_threads(
    access_token: str,
    threads_user_id: str,
    caption: str,
    image_url: str,
) -> dict:
    """
    Post image + caption to Threads.
    Two-step: create container → publish.
    """

    print("=" * 40)
    print("THREADS: creating media container")
    print("USER ID:", threads_user_id)
    print("IMAGE URL:", image_url)
    print("=" * 40)

    base_url = f"https://graph.threads.net/v1.0/{threads_user_id}"

    # ── Step 1: Create container ──────────────────────
    container_resp = requests.post(
        f"{base_url}/threads",
        params={
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    container_data = container_resp.json()
    print("THREADS CONTAINER:", container_data)

    if "id" not in container_data:
        return {
            "success": False,
            "error": "Threads container creation failed",
            "details": container_data,
        }

    creation_id = container_data["id"]

    # ── Step 2: Publish ───────────────────────────────
    publish_resp = requests.post(
        f"{base_url}/threads_publish",
        params={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish_data = publish_resp.json()
    print("THREADS PUBLISH:", publish_data)

    if "id" not in publish_data:
        return {
            "success": False,
            "error": "Threads publish failed",
            "details": publish_data,
        }

    return {
        "success": True,
        "platform": "threads",
        "post_id": publish_data["id"],
    }