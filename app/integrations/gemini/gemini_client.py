import requests
import urllib.parse
import random
from app.core.config import settings


# Models to try in order — first working one is used
CANDIDATE_MODELS = [
    ("gemini-2.5-flash-image",            "generateContent", "v1beta"),
    ("gemini-3.1-flash-image-preview",    "generateContent", "v1beta"),
    ("gemini-3-pro-image-preview",        "generateContent", "v1beta"),
    ("gemini-2.5-flash-image",            "generateContent", "v1"),
    ("gemini-3.1-flash-image-preview",    "generateContent", "v1"),
]

_working_model = None  # cached after first successful call


def _find_working_model(api_key: str) -> tuple | None:
    """Try each model and return the first one that works."""
    global _working_model
    if _working_model:
        return _working_model

    prompt = "a beautiful sunset, test image"

    for model, method, version in CANDIDATE_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/{version}/models/"
            f"{model}:{method}?key={api_key}"
        )
        try:
            resp = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"]},
                },
                timeout=30,
            )
            print(f"MODEL TEST {model} ({version}): HTTP {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                has_image = any(
                    "inlineData" in part
                    for c in data.get("candidates", [])
                    for part in c.get("content", {}).get("parts", [])
                )
                if has_image:
                    print(f"✅ WORKING MODEL: {model} ({version})")
                    _working_model = (model, method, version)
                    return _working_model
        except Exception as e:
            print(f"MODEL TEST {model} error: {e}")

    return None


def generate_images(prompt: str, count: int = 1) -> list[str]:
    """
    Generate images using the first available free Gemini image model.
    Uploads to ImgBB for public URLs.
    Falls back to Pollinations if no Gemini model works.
    """

    print("=" * 40)
    print(f"GEMINI: generating {count} image(s)")
    print(f"PROMPT: {prompt[:80]}")
    print("=" * 40)

    # If no API keys, use Pollinations
    if not settings.GEMINI_API_KEY or not settings.IMGBB_API_KEY:
        print("GEMINI: missing API keys, using Pollinations fallback")
        return _pollinations_fallback(prompt, count)

    # Find working model (cached after first call)
    working = _find_working_model(settings.GEMINI_API_KEY)
    if not working:
        print("GEMINI: no working model found, using Pollinations fallback")
        return _pollinations_fallback(prompt, count)

    model, method, version = working
    urls = []

    for i in range(count):
        varied_prompt = (
            f"{prompt}, unique creative style variation {i + 1}, "
            "high quality, vibrant, aesthetic, social media ready"
        )
        print(f"GEMINI: generating image {i + 1}/{count} with {model}")

        url = (
            f"https://generativelanguage.googleapis.com/{version}/models/"
            f"{model}:{method}?key={settings.GEMINI_API_KEY}"
        )

        try:
            response = requests.post(
                url,
                json={
                    "contents": [{"parts": [{"text": varied_prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"]},
                },
                timeout=60,
            )

            print(f"GEMINI HTTP STATUS: {response.status_code}")
            data = response.json()

            if response.status_code != 200:
                raise Exception(data.get("error", {}).get("message", str(data)))

            # Extract base64 image
            b64_data = None
            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        b64_data = part["inlineData"]["data"]
                        break
                if b64_data:
                    break

            if not b64_data:
                raise Exception(f"No image in response: {data}")

            print(f"GEMINI: got image {i + 1}, uploading to ImgBB...")
            public_url = _upload_to_imgbb(b64_data, f"post_img_{i + 1}")
            print(f"IMGBB URL: {public_url}")
            urls.append(public_url)

        except Exception as e:
            print(f"GEMINI ERROR for image {i + 1}: {e}")
            # Fallback for this image only
            urls.append(_pollinations_fallback(prompt, 1)[0])

    return urls


def _upload_to_imgbb(b64_data: str, name: str = "image") -> str:
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": settings.IMGBB_API_KEY,
            "image": b64_data,
            "name": name,
        },
        timeout=30,
    )
    data = response.json()
    if not data.get("success"):
        raise Exception(f"ImgBB upload failed: {data}")
    return data["data"]["display_url"]


def _pollinations_fallback(prompt: str, count: int) -> list[str]:
    """Free fallback — always works, returns public URLs."""
    encoded = urllib.parse.quote(prompt)
    return [
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?nologo=true&width=1080&height=1080&seed={random.randint(1000,999999)}"
        for _ in range(count)
    ]