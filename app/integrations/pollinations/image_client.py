import urllib.parse

async def generate_image(prompt: str):

    encoded = urllib.parse.quote(prompt)

    return (
        "https://image.pollinations.ai/prompt/"
        f"{encoded}"
    )