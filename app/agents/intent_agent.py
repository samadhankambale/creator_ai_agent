def parse(message: str):
    
    # You can use Groq here too OR rules first
    prompt = f"""
    Extract:
    - platforms (instagram, linkedin, both)
    - content type
    - image needed yes/no

    Message: {message}
    """

    response = groq_client.chat(prompt)

    return response