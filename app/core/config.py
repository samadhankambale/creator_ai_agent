import os
from dotenv import load_dotenv

load_dotenv()

class Settings:

    DATABASE_URL = os.getenv("DATABASE_URL")
    REDIS_URL = os.getenv("REDIS_URL")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")

    META_APP_ID = os.getenv("META_APP_ID")
    META_APP_SECRET = os.getenv("META_APP_SECRET")
    META_REDIRECT_URI = os.getenv("META_REDIRECT_URI")

    WHATSAPP_VERIFY_TOKEN = os.getenv(
        "WHATSAPP_VERIFY_TOKEN"
    )

    WHATSAPP_ACCESS_TOKEN = os.getenv(
        "WHATSAPP_ACCESS_TOKEN"
    )

    WHATSAPP_PHONE_NUMBER_ID = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID"
    )

    LINKEDIN_CLIENT_ID = os.getenv(
        "LINKEDIN_CLIENT_ID"
    )

    LINKEDIN_CLIENT_SECRET = os.getenv(
        "LINKEDIN_CLIENT_SECRET"
    )

    LINKEDIN_REDIRECT_URI = os.getenv(
        "LINKEDIN_REDIRECT_URI"
    )

settings = Settings()