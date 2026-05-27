import requests


def post_to_threads(
    access_token: str,
    threads_user_id: str,
    caption: str,
    image_url: str,
    extra_image_urls: list = None,
    video_url: str = None,
) -> dict:
    all_images = [image_url] + (extra_image_urls or [])

    if video_url:
        return _post_video(access_token, threads_user_id, video_url, caption)

    if len(all_images) > 1:
        return _post_carousel(access_token, threads_user_id, all_images, caption)

    return _post_single(access_token, threads_user_id, image_url, caption)


def _post_single(access_token: str, user_id: str, image_url: str, caption: str) -> dict:
    base = f"https://graph.threads.net/v1.0/{user_id}"
    caption = caption[:500]

    resp = requests.post(
        f"{base}/threads",
        params={
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    data = resp.json()
    print("THREADS CONTAINER:", data)

    if "id" not in data:
        return {"success": False, "error": "Threads container failed", "details": data}

    return _publish(access_token, user_id, data["id"])


def _post_video(access_token: str, user_id: str, video_url: str, caption: str) -> dict:
    base = f"https://graph.threads.net/v1.0/{user_id}"
    caption = caption[:500]

    resp = requests.post(
        f"{base}/threads",
        params={
            "media_type": "VIDEO",
            "video_url": video_url,
            "text": caption,
            "access_token": access_token,
        },
        timeout=60,
    )
    data = resp.json()
    print("THREADS VIDEO CONTAINER:", data)

    if "id" not in data:
        return {"success": False, "error": "Threads video container failed", "details": data}

    container_id = data["id"]

    # Wait for video processing before publishing
    print("THREADS: waiting for video processing...")
    import time
    for attempt in range(12):  # max 60 seconds
        time.sleep(5)
        status_resp = requests.get(
            f"https://graph.threads.net/v1.0/{container_id}",
            params={"fields": "status,error_message", "access_token": access_token},
            timeout=30,
        )
        status_data = status_resp.json()
        status = status_data.get("status", "")
        print(f"THREADS VIDEO STATUS ({attempt+1}): {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            return {"success": False, "error": "Threads video processing failed",
                    "details": status_data.get("error_message", "")}

    return _publish(access_token, user_id, container_id)


def _post_carousel(access_token: str, user_id: str, image_urls: list, caption: str) -> dict:
    base = f"https://graph.threads.net/v1.0/{user_id}"
    caption = caption[:500]

    child_ids = []
    for url in image_urls:
        resp = requests.post(
            f"{base}/threads",
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
            return {"success": False, "error": "Threads carousel child failed", "details": data}
        child_ids.append(data["id"])

    # Wait for children to be ready before creating carousel
    import time
    time.sleep(5)

    carousel_resp = requests.post(
        f"{base}/threads",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "text": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    carousel = carousel_resp.json()
    print("THREADS CAROUSEL:", carousel)

    if "id" not in carousel:
        return {"success": False, "error": "Threads carousel failed", "details": carousel}

    return _publish(access_token, user_id, carousel["id"])


def _publish(access_token: str, user_id: str, creation_id: str) -> dict:
    resp = requests.post(
        f"https://graph.threads.net/v1.0/{user_id}/threads_publish",
        params={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    data = resp.json()
    print("THREADS PUBLISH:", data)

    if "id" not in data:
        return {"success": False, "error": "Threads publish failed", "details": data}

    return {"success": True, "platform": "threads", "post_id": data["id"]}