"""
Intent detection using Groq.
Handles all possible user messages intelligently.
"""
import httpx
import json
import random
from app.core.config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

INTENT_PROMPT = """You are an intent classifier for a social media posting bot on WhatsApp.

Classify the user message into ONE of these intents:

- "create_post" — user wants to create/schedule a social media post
- "generate_image" — user wants to generate an image/photo (without explicitly posting)
- "question" — user asks about bot features, platforms, or how things work
- "post_history" — user asks about their previous posts (what did I post, show my posts)
- "cancel_schedule" — user wants to cancel a scheduled post
- "retry" — user wants to retry a failed post
- "discard" — user wants to cancel/discard current draft
- "resume" — user wants to continue a previous draft
- "greeting" — hi, hello, hey, how are you
- "off_topic" — completely unrelated (news, politics, weather, general knowledge, sports, cooking recipes, etc.)

Rules:
- "generate_image" if user says: generate image, create photo, make a picture, draw, generate a photo of X
- "create_post" if user mentions posting, sharing, publishing, or a topic to post about
- "off_topic" for anything unrelated to social media, images, or posting
- "question" only for bot/platform related questions

If intent is "question", provide a helpful "answer" about:
- Instagram: image posts, carousel (up to 10), reels (video only), image stories
- LinkedIn: image posts, carousel — NO video, NO stories
- Threads: image posts, video posts, carousel — NO stories
- Twitter: requires paid Basic plan ($100/mo)
- Video stories: NOT supported on any platform via API

Return ONLY valid JSON:
{
  "intent": "create_post|generate_image|question|post_history|cancel_schedule|retry|discard|resume|greeting|off_topic",
  "answer": "helpful answer if intent is question, else null",
  "image_subject": "what to generate if intent is generate_image, else null",
  "confidence": 0.0-1.0
}

User message:
"""

BOT_CAPABILITIES = """🤖 *What I can do:*

*Create posts:*
• Send any topic → I generate caption + image
• Send your own image/video → I generate caption
• Post on Instagram, LinkedIn, Threads, Twitter

*Post types:*
• 📸 Regular Post — all platforms
• 🎠 Carousel — Instagram, LinkedIn, Threads
• 🎬 Reel — Instagram only (video)
• ⭕ Story — Instagram only (image)

*Other features:*
• 🖼 Generate images from description
• 🕐 Schedule posts for any time
• ✍️ AI caption generation
• 💾 Auto-saves drafts — resume anytime
• 📊 View post history

Type *help* anytime to see this."""

OFF_TOPIC_RESPONSES = [
    "I'm a social media posting assistant — I can only help you create and publish posts! 😊\n\nSend me a topic and I'll create a post, or type *help* to see what I can do.",
    "That's outside my expertise! I specialize in social media posting.\n\nWant to create a post? Just send me any topic!",
    "I can't help with that, but I'm great at creating social media posts! 📱\n\nSend me any topic and I'll generate a caption and image for you.",
]


def get_off_topic_response() -> str:
    return random.choice(OFF_TOPIC_RESPONSES)


async def detect_intent(message: str) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a JSON intent classifier. Return only valid JSON."},
            {"role": "user", "content": INTENT_PROMPT + message},
        ],
        "temperature": 0.1,
        "max_tokens": 300,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        print(f"INTENT: {result.get('intent')} | confidence={result.get('confidence')}")
        return result
    except Exception as e:
        print(f"INTENT DETECTION ERROR: {e}")
        return {"intent": "unknown", "answer": None, "image_subject": None, "confidence": 0.0}