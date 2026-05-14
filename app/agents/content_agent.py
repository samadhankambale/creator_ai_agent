def generate_caption(intent):
    
    prompt = f"""
    Create a short viral caption for:
    type: {intent["content_type"]}
    tone: motivational
    platform: social media
    """

    return groq_client.chat(prompt)


def generate_image(intent):
    
    prompt = f"motivational quote aesthetic background minimal dark"

    return f"https://image.pollinations.ai/prompt/{prompt}"