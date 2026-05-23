"""
Image generation provider.

Switch provider by changing IMAGE_PROVIDER in .env:
  IMAGE_PROVIDER=pollinations   (default, free, no API key needed)
  IMAGE_PROVIDER=gemini         (requires GEMINI_API_KEY + IMGBB_API_KEY)

No code changes needed to switch — just update .env and restart.
"""
import urllib.parse
import random
import requests
from app.core.config import settings


def generate_images(prompt: str, count: int = 1) -> list[str]:
    """
    Generate `count` image variations.
    Returns list of public URLs ready for Instagram/LinkedIn/Threads.
    """
    provider = getattr(settings, "IMAGE_PROVIDER", "pollinations").lower().strip()
    print(f"IMAGE PROVIDER: {provider}")

    if provider == "gemini":
        return _gemini(prompt, count)
    else:
        return _pollinations(prompt, count)


# ──────────────────────────────────────────────────────────────
# POLLINATIONS (current default — free, no API key)
# ──────────────────────────────────────────────────────────────

def _pollinations(prompt: str, count: int) -> list[str]:
    encoded = urllib.parse.quote(prompt)
    urls = []
    for _ in range(count):
        seed = random.randint(1000, 999999)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?nologo=true&width=1080&height=1080&seed={seed}&enhance=true"
        )
        urls.append(url)
    print(f"POLLINATIONS: generated {count} URL(s)")
    return urls


# ──────────────────────────────────────────────────────────────
# GEMINI + IMGBB (switch to this later)
# ──────────────────────────────────────────────────────────────

# Free models to try in order
_GEMINI_MODELS = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
]

_working_gemini_model = None  # cached after first successful call


def _gemini(prompt: str, count: int) -> list[str]:
    global _working_gemini_model

    if not settings.GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY not set in .env")
    if not settings.IMGBB_API_KEY:
        raise Exception("IMGBB_API_KEY not set in .env")

    # Find working model on first call
    if not _working_gemini_model:
        _working_gemini_model = _find_gemini_model()
        if not _working_gemini_model:
            raise Exception(
                "No working Gemini image model found. "
                "Check your API key quota or switch IMAGE_PROVIDER=pollinations"
            )

    urls = []
    for i in range(count):
        varied = f"{prompt}, unique variation {i + 1}, high quality, vibrant, aesthetic"
        b64 = _gemini_generate(varied, _working_gemini_model)
        url = _imgbb_upload(b64, f"img_{i + 1}")
        urls.append(url)
        print(f"GEMINI: image {i + 1} → {url}")

    return urls


def _find_gemini_model() -> str | None:
    """Test each model and return the first that works."""
    test_prompt = "a beautiful landscape, test"
    for model in _GEMINI_MODELS:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={settings.GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": test_prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE"]},
                },
                timeout=30,
            )
            print(f"GEMINI MODEL TEST {model}: HTTP {resp.status_code}")
            if resp.status_code == 429:
                raise Exception("Gemini quota exceeded. Try again later or use IMAGE_PROVIDER=pollinations")
            if resp.status_code == 200:
                data = resp.json()
                has_image = any(
                    "inlineData" in part
                    for c in data.get("candidates", [])
                    for part in c.get("content", {}).get("parts", [])
                )
                if has_image:
                    print(f"✅ GEMINI WORKING MODEL: {model}")
                    return model
        except Exception as e:
            if "quota" in str(e).lower():
                raise
            print(f"GEMINI MODEL {model} error: {e}")
    return None


def _gemini_generate(prompt: str, model: str) -> str:
    """Call Gemini and return base64 image data."""
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={settings.GEMINI_API_KEY}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        },
        timeout=60,
    )
    print(f"GEMINI GENERATE HTTP: {resp.status_code}")
    data = resp.json()

    if resp.status_code != 200:
        raise Exception(data.get("error", {}).get("message", str(data)))

    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                return part["inlineData"]["data"]

    raise Exception(f"Gemini returned no image. Response: {data}")


def _imgbb_upload(b64_data: str, name: str = "image") -> str:
    """Upload base64 image to ImgBB and return public URL."""
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": settings.IMGBB_API_KEY, "image": b64_data, "name": name},
        timeout=30,
    )
    data = resp.json()
    if not data.get("success"):
        raise Exception(f"ImgBB upload failed: {data}")
    return data["data"]["display_url"]