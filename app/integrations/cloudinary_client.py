"""
Cloudinary media hosting.
Uploads WhatsApp images/videos to get public URLs for Instagram, Threads etc.
"""
import requests
import base64
import hashlib
import time
from app.core.config import settings


def upload_media(media_bytes: bytes, media_type: str = "image", filename: str = "media") -> str:
    """
    Upload image or video bytes to Cloudinary.
    Returns public HTTPS URL.
    media_type: "image" or "video"
    """
    print(f"CLOUDINARY: uploading {media_type} ({len(media_bytes)} bytes)")

    cloud_name = settings.CLOUDINARY_CLOUD_NAME
    api_key = settings.CLOUDINARY_API_KEY
    api_secret = settings.CLOUDINARY_API_SECRET

    if not cloud_name or not api_key or not api_secret:
        raise Exception("Cloudinary credentials not set in .env")

    # Generate signature
    timestamp = int(time.time())
    params_to_sign = f"timestamp={timestamp}"
    signature = hashlib.sha1(
        f"{params_to_sign}{api_secret}".encode()
    ).hexdigest()

    # Encode bytes to base64
    b64_data = base64.b64encode(media_bytes).decode("utf-8")

    # Determine mime type
    if media_type == "video":
        data_uri = f"data:video/mp4;base64,{b64_data}"
    else:
        data_uri = f"data:image/jpeg;base64,{b64_data}"

    response = requests.post(
        f"https://api.cloudinary.com/v1_1/{cloud_name}/{media_type}/upload",
        data={
            "file": data_uri,
            "api_key": api_key,
            "timestamp": str(timestamp),
            "signature": signature,
        },
        timeout=120,
    )

    print(f"CLOUDINARY STATUS: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        url = data.get("secure_url")
        if url:
            print(f"CLOUDINARY URL: {url}")
            return url
        raise Exception(f"No URL in Cloudinary response: {data}")

    try:
        error = response.json()
    except Exception:
        error = response.text

    raise Exception(f"Cloudinary upload failed {response.status_code}: {error}")


def upload_from_url(media_url: str, media_type: str = "image") -> str:
    """Upload media from a public URL to Cloudinary."""
    print(f"CLOUDINARY: fetching from URL for {media_type}")

    cloud_name = settings.CLOUDINARY_CLOUD_NAME
    api_key = settings.CLOUDINARY_API_KEY
    api_secret = settings.CLOUDINARY_API_SECRET

    timestamp = int(time.time())
    params_to_sign = f"timestamp={timestamp}"
    signature = hashlib.sha1(
        f"{params_to_sign}{api_secret}".encode()
    ).hexdigest()

    response = requests.post(
        f"https://api.cloudinary.com/v1_1/{cloud_name}/{media_type}/upload",
        data={
            "file": media_url,
            "api_key": api_key,
            "timestamp": str(timestamp),
            "signature": signature,
        },
        timeout=120,
    )

    if response.status_code == 200:
        url = response.json().get("secure_url")
        if url:
            return url

    raise Exception(f"Cloudinary URL upload failed: {response.text}")