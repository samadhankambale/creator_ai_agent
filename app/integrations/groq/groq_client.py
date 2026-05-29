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
                    "You are a social media expert who writes captions strictly about the given topic.\n"
                    "Rules:\n"
                    "- Write ONE caption ONLY about the specific topic provided.\n"
                    "- Output ONLY the caption text. Nothing else.\n"
                    "- NO explanations, NO image descriptions, NO numbering, NO options.\n"
                    "- Include 3-5 relevant hashtags at the END only.\n"
                    "- Keep it under 300 characters total.\n"
                    "- Make it engaging, specific to the topic, and insightful.\n"
                    "- Never write generic captions like 'connecting the world' unless that is the topic.\n"
                    "- If topic is about a person, place, technology or event — write specifically about that.\n"
                    "- Ignore any words like 'generate', 'images', 'post about' in the prompt — focus on the TOPIC only."
                ),
            },
            {"role": "user", "content": f"Topic: {prompt}"},
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)

    data = resp.json()
    print("GROQ RESPONSE:", data)

    if "choices" not in data:
        raise Exception(f"Groq error: {data}")

    caption = data["choices"][0]["message"]["content"].strip()

    # Remove multi-caption patterns
    if any(x in caption for x in ["Image 1:", "Option 1:", "*Image", "Caption 1:"]):
        lines = [l.strip() for l in caption.split("\n") if l.strip()]
        caption = lines[0] if lines else caption

    return caption