import requests


def post_to_threads(
    access_token: str,
    threads_user_id: str,
    caption: str,
    image_url: str,
    extra_image_urls: list = None,
) -> dict:

    all_images = [image_url] + (extra_image_urls or [])

    print("=" * 40)
    print(f"THREADS: posting with {len(all_images)} image(s)")
    print("USER ID:", threads_user_id)
    print("=" * 40)

    if len(all_images) > 1:
        return _post_carousel(access_token, threads_user_id, all_images, caption)
    else:
        return _post_single(access_token, threads_user_id, image_url, caption)


def _post_single(access_token: str, user_id: str, image_url: str, caption: str) -> dict:
    base_url = f"https://graph.threads.net/v1.0/{user_id}"
    caption = caption[:500]  # Threads limit

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

    return _publish(access_token, user_id, container_data["id"])


def _post_carousel(
    access_token: str,
    user_id: str,
    image_urls: list,
    caption: str,
) -> dict:
    base_url = f"https://graph.threads.net/v1.0/{user_id}"
    caption = caption[:500]  # Threads limit

    # Step 1: create child containers
    child_ids = []
    for url in image_urls:
        resp = requests.post(
            f"{base_url}/threads",
            params={
                "media_type": "IMAGE",
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": access_token,
            },
            timeout=30,
        )
        data = resp.json()
        print("THREADS CHILD:", data)
        if "id" not in data:
            return {
                "success": False,
                "error": "Threads carousel child failed",
                "details": data,
            }
        child_ids.append(data["id"])

    # Step 2: create carousel container
    carousel_resp = requests.post(
        f"{base_url}/threads",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "text": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    carousel_data = carousel_resp.json()
    print("THREADS CAROUSEL:", carousel_data)

    if "id" not in carousel_data:
        return {
            "success": False,
            "error": "Threads carousel creation failed",
            "details": carousel_data,
        }

    return _publish(access_token, user_id, carousel_data["id"])


def _publish(access_token: str, user_id: str, creation_id: str) -> dict:
    publish_resp = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
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