"""
Entity extraction using Groq.
Silently extracts all available info from the user's first message.
Only asks for what's genuinely missing.
"""
import json
import httpx
from app.core.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACTION_PROMPT = """
You are an entity extractor for a social media post creation bot.
Extract ALL available information from the user's message.

Return a JSON object with these fields (use null if not mentioned):
{
  "topic": "main subject/topic of the post",
  "platforms": ["instagram", "linkedin", "threads", "twitter"] or null,
  "post_type": "post" | "story" | "reel" | null,
  "image_count": integer or null,
  "caption_instruction": "any specific caption requirements mentioned",
  "schedule": "raw schedule text like 'tomorrow 8pm' or 'after 2 hours'" or null,
  "tone": "motivational" | "professional" | "casual" | "witty" | null,
  "hashtags": ["tag1", "tag2"] or [],
  "language": "english" by default or detected language,
  "cta": "call to action if mentioned" or null
}

Rules:
- Platform names: only these values: instagram, linkedin, threads, twitter
- If user says "all platforms" → ["instagram", "linkedin", "threads", "twitter"]
- If user says "story" → post_type = "story", platforms must include "instagram"
- If user says "reel" → post_type = "reel", platforms must include "instagram"
- If user says "carousel" or "multiple images" → post_type = "post", image_count >= 2
- Extract numbers for image count (e.g. "3 images" → image_count: 3)
- Keep topic concise — the actual subject, not the full sentence
- Return ONLY valid JSON, no markdown, no explanation

User message:
"""


async def extract_entities(message: str) -> dict:
    """
    Extract entities from user message using Groq.
    Returns dict with extracted fields (null for missing).
    """
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "You are a JSON entity extractor. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": EXTRACTION_PROMPT + message,
            },
        ],
        "temperature": 0.1,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)

        data = resp.json()
        raw = data["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        extracted = json.loads(raw)
        print("EXTRACTED ENTITIES:", extracted)
        return extracted

    except Exception as e:
        print(f"ENTITY EXTRACTION ERROR: {e}")
        return {}


def get_missing_fields(extracted: dict) -> list:
    """
    Only ask for topic if missing.
    Everything else has smart defaults:
    - image_count: defaults to 1
    - platforms: asked after content generation
    - schedule: defaults to post now
    """
    missing = []
    if not extracted.get("topic"):
        missing.append("topic")
    return missing


def build_missing_fields_message(missing: list) -> str:
    """Build a conversational message asking only for missing fields."""
    if "topic" in missing and "image_count" in missing:
        return (
            "What would you like to post about, and how many images do you want? (1-5)\n\n"
            "💡 Or send your own image directly in chat."
        )
    if "topic" in missing:
        return "What would you like to post about?"
    if "image_count" in missing:
        return (
            "How many images do you want? (1-5)\n\n"
            "💡 Or send your own image in chat."
        )
    return ""