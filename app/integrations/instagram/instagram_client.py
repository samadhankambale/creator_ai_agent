import requests

GRAPH_URL = "https://graph.facebook.com/v20.0"


def post_to_instagram(
    access_token: str,
    platform_user_id: str,
    image_url: str,
    caption: str,
    ig_user_id: str = None,
    extra_image_urls: list = None,
) -> dict:
    """
    Single image or carousel post to Instagram.
    If extra_image_urls provided → carousel post.
    """

    user_id = platform_user_id or ig_user_id
    all_images = [image_url] + (extra_image_urls or [])

    if len(all_images) > 1:
        return _post_carousel(access_token, user_id, all_images, caption)
    else:
        return _post_single(access_token, user_id, image_url, caption)


def _post_single(access_token: str, user_id: str, image_url: str, caption: str) -> dict:
    print("INSTAGRAM: single image post")

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
    print("INSTAGRAM CONTAINER:", container_data)

    if "id" not in container_data:
        return {
            "success": False,
            "error": "Media container creation failed",
            "details": container_data,
        }

    return _publish(access_token, user_id, container_data["id"])


def _post_carousel(
    access_token: str,
    user_id: str,
    image_urls: list,
    caption: str,
) -> dict:
    print(f"INSTAGRAM: carousel post with {len(image_urls)} images")

    # Step 1: create child containers for each image
    child_ids = []
    for url in image_urls:
        resp = requests.post(
            f"{GRAPH_URL}/{user_id}/media",
            data={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": access_token,
            },
            timeout=30,
        )
        data = resp.json()
        print("INSTAGRAM CHILD CONTAINER:", data)
        if "id" not in data:
            return {
                "success": False,
                "error": "Carousel child container failed",
                "details": data,
            }
        child_ids.append(data["id"])

    # Step 2: create carousel container
    carousel_resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    carousel_data = carousel_resp.json()
    print("INSTAGRAM CAROUSEL CONTAINER:", carousel_data)

    if "id" not in carousel_data:
        return {
            "success": False,
            "error": "Carousel container creation failed",
            "details": carousel_data,
        }

    return _publish(access_token, user_id, carousel_data["id"])


def _publish(access_token: str, user_id: str, creation_id: str) -> dict:
    publish_resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    publish_data = publish_resp.json()
    print("INSTAGRAM PUBLISH:", publish_data)

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