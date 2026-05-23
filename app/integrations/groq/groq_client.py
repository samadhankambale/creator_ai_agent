import httpx
from app.core.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def generate_caption(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a social media expert. "
                    "Your job is to write ONE single viral caption for a social media post. "
                    "Rules:\n"
                    "- Output ONLY the caption text. Nothing else.\n"
                    "- NO explanations, NO image descriptions, NO numbering, NO options.\n"
                    "- Include 3-5 relevant hashtags at the end.\n"
                    "- Keep it under 400 characters total.\n"
                    "- Make it engaging and punchy.\n"
                    "If the user message contains words like 'generate images' or numbers, "
                    "ignore them and write a caption about the TOPIC mentioned."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)

    data = resp.json()
    print("GROQ RESPONSE:", data)

    if "choices" not in data:
        raise Exception(f"Groq error: {data}")

    caption = data["choices"][0]["message"]["content"].strip()

    # Safety trim — remove any accidental multi-caption output
    # If it contains "Image 1:" or "Option 1:" patterns, take only first line block
    if "Image 1:" in caption or "Option 1:" in caption or "*Image" in caption:
        # Take only the first sentence/paragraph
        lines = [l.strip() for l in caption.split("\n") if l.strip()]
        caption = lines[0] if lines else caption

    return caption