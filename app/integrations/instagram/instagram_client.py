import requests
import time

GRAPH_URL = "https://graph.facebook.com/v20.0"


def post_to_instagram(
    access_token: str,
    platform_user_id: str,
    image_url: str,
    caption: str,
    extra_image_urls: list = None,
    post_type: str = "post",  # post | reel | story
    video_url: str = None,
) -> dict:
    """
    Post to Instagram.
    post_type:
      post  — image or carousel feed post
      reel  — video reel
      story — image or video story
    """
    user_id = platform_user_id

    if post_type in ("reel", "video") or (video_url and post_type == "post"):
        if not video_url:
            return {"success": False, "error": "Video URL required for video/reel posts"}
        return _post_reel(access_token, user_id, video_url, caption)

    if post_type == "story":
        media_url = video_url or image_url
        media_type = "VIDEO" if video_url else "IMAGE"
        return _post_story(access_token, user_id, media_url, media_type)

    # Default: feed post
    all_images = [image_url] + (extra_image_urls or [])
    if len(all_images) > 1:
        return _post_carousel(access_token, user_id, all_images, caption)
    else:
        return _post_single(access_token, user_id, image_url, caption, video_url)


def _post_single(
    access_token: str,
    user_id: str,
    image_url: str,
    caption: str,
    video_url: str = None,
) -> dict:
    print("INSTAGRAM: single post")

    if video_url:
        data = {
            "media_type": "VIDEO",
            "video_url": video_url,
            "caption": caption,
            "access_token": access_token,
        }
    else:
        data = {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        }

    resp = requests.post(f"{GRAPH_URL}/{user_id}/media", data=data, timeout=60)
    container = resp.json()
    print("INSTAGRAM CONTAINER:", container)

    if "id" not in container:
        return {"success": False, "error": "Container creation failed", "details": container}

    # For video, wait for processing
    if video_url:
        _wait_for_video(access_token, container["id"])

    return _publish(access_token, user_id, container["id"])


def _post_carousel(access_token: str, user_id: str, image_urls: list, caption: str) -> dict:
    print(f"INSTAGRAM: carousel with {len(image_urls)} images")

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
        if "id" not in data:
            return {"success": False, "error": "Carousel child failed", "details": data}
        child_ids.append(data["id"])

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
    carousel = carousel_resp.json()
    print("INSTAGRAM CAROUSEL:", carousel)

    if "id" not in carousel:
        return {"success": False, "error": "Carousel creation failed", "details": carousel}

    return _publish(access_token, user_id, carousel["id"])


def _post_reel(access_token: str, user_id: str, video_url: str, caption: str) -> dict:
    print("INSTAGRAM: reel post")

    resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": access_token,
        },
        timeout=60,
    )
    container = resp.json()
    print("INSTAGRAM REEL CONTAINER:", container)

    if "id" not in container:
        return {"success": False, "error": "Reel container failed", "details": container}

    _wait_for_video(access_token, container["id"])
    return _publish(access_token, user_id, container["id"])


def _post_story(
    access_token: str,
    user_id: str,
    media_url: str,
    media_type: str = "IMAGE",
) -> dict:
    print(f"INSTAGRAM: story ({media_type})")

    # Instagram deprecated VIDEO type for stories
    # Video stories must use REELS media_type
    if media_type == "VIDEO":
        print("INSTAGRAM: video story → using REELS media type")
        data = {
            "media_type": "REELS",
            "video_url": media_url,
            "share_to_feed": "false",  # story only, not feed
            "access_token": access_token,
        }
    else:
        data = {
            "image_url": media_url,
            "media_type": "STORIES",
            "access_token": access_token,
        }

    resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media",
        data=data,
        timeout=60,
    )
    container = resp.json()
    print("INSTAGRAM STORY CONTAINER:", container)

    if "id" not in container:
        return {"success": False, "error": "Story container failed", "details": container}

    if media_type == "VIDEO":
        _wait_for_video(access_token, container["id"])

    return _publish(access_token, user_id, container["id"])


def _wait_for_video(access_token: str, container_id: str, max_wait: int = 120):
    """
    Wait for Instagram to finish processing the video.
    Instagram requires polling until status_code = FINISHED.
    Typical wait: 15-60 seconds depending on video size.
    """
    print(f"INSTAGRAM: waiting for video processing (max {max_wait}s)...")
    for attempt in range(max_wait // 5):
        resp = requests.get(
            f"{GRAPH_URL}/{container_id}",
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=30,
        )
        data = resp.json()

        # Handle authorization error (code 33) = container not ready yet, keep waiting
        if "error" in data:
            err = data["error"]
            subcode = err.get("error_subcode") or err.get("code", 0)
            if subcode == 33:
                print(f"INSTAGRAM: container not ready yet ({attempt+1}) — waiting 5s...")
                time.sleep(5)
                continue
            # Other error — stop waiting
            print(f"INSTAGRAM: status check error: {data}")
            return False

        status = data.get("status_code") or data.get("status") or ""
        print(f"INSTAGRAM VIDEO STATUS ({attempt+1}): {status!r}")

        if status in ("FINISHED", "PUBLISHED"):
            print("INSTAGRAM: video ready!")
            return True
        if status == "ERROR":
            raise Exception(f"Instagram video processing failed: {data}")

        time.sleep(5)

    print("INSTAGRAM: video processing timeout after 120s — attempting publish anyway")
    return False


def _publish(access_token: str, user_id: str, creation_id: str) -> dict:
    resp = requests.post(
        f"{GRAPH_URL}/{user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    data = resp.json()
    print("INSTAGRAM PUBLISH:", data)

    if "id" not in data:
        return {"success": False, "error": "Publish failed", "details": data}

    return {"success": True, "platform": "instagram", "post_id": data["id"]}