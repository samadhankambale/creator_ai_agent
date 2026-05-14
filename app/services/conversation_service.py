async def detect_intent(message: str):

    message = message.lower()

    if "connect instagram" in message:
        return "connect_instagram"

    if "connect linkedin" in message:
        return "connect_linkedin"

    if "schedule" in message:
        return "schedule"

    if message == "1":
        return "approve"

    if message == "2":
        return "schedule"

    if message == "3":
        return "regenerate"

    return "generate"