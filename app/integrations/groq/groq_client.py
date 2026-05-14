import httpx

from app.core.config import settings

async def generate_caption(prompt: str):

    url = (
        "https://api.groq.com/openai/v1/"
        "chat/completions"
    )

    headers = {
        "Authorization":
        f"Bearer {settings.GROQ_API_KEY}",

        "Content-Type":
        "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",

        "messages": [
            {
                "role": "system",
                "content":
                "You are a social media expert."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    async with httpx.AsyncClient(
        timeout=60.0
    ) as client:

        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

    data = response.json()

    if "choices" not in data:
        raise Exception(data)

    return data["choices"][0]["message"]["content"]