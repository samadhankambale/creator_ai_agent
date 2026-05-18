from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict
)


class Settings(BaseSettings):

    # ==================================================
    # DATABASE
    # ==================================================

    DATABASE_URL: str

    REDIS_URL: str

    # ==================================================
    # SECURITY
    # ==================================================

    ENCRYPTION_KEY: str

    # ==================================================
    # GROQ
    # ==================================================

    GROQ_API_KEY: str

    # ==================================================
    # WHATSAPP
    # ==================================================

    WHATSAPP_ACCESS_TOKEN: str

    WHATSAPP_PHONE_NUMBER_ID: str

    WHATSAPP_VERIFY_TOKEN: str

    # ==================================================
    # META
    # ==================================================

    META_APP_ID: str

    META_APP_SECRET: str

    META_REDIRECT_URI: str

    # ==================================================
    # LINKEDIN
    # ==================================================

    LINKEDIN_CLIENT_ID: str = ""

    LINKEDIN_CLIENT_SECRET: str = ""

    LINKEDIN_REDIRECT_URI: str = ""

    # ==================================================
    # PYDANTIC CONFIG
    # ==================================================
    
    # ============================================
    # APP URL
    # ============================================

    APP_BASE_URL: str

    model_config = SettingsConfigDict(

        env_file=".env",

        extra="allow"
    )


settings = Settings()


# from pydantic_settings import BaseSettings
# import os
# from dotenv import load_dotenv

# load_dotenv()

# class Settings(BaseSettings):

#     DATABASE_URL: str

#     REDIS_URL: str

#     ENCRYPTION_KEY: str

#     GROQ_API_KEY: str

#     WHATSAPP_ACCESS_TOKEN: str

#     WHATSAPP_PHONE_NUMBER_ID: str

#     WHATSAPP_VERIFY_TOKEN: str

#     META_APP_ID: str

#     META_APP_SECRET: str

#     META_REDIRECT_URI: str

#     LINKEDIN_CLIENT_ID: str = ""

#     LINKEDIN_CLIENT_SECRET: str = ""

#     LINKEDIN_REDIRECT_URI: str = ""

#     class Config:

#         env_file = ".env"


# settings = Settings()


# # import os
# # from dotenv import load_dotenv

# # load_dotenv()

# # class Settings:

# #     DATABASE_URL = os.getenv("DATABASE_URL")
# #     REDIS_URL = os.getenv("REDIS_URL")

# #     GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# #     ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")

# #     META_APP_ID = os.getenv("META_APP_ID")
# #     META_APP_SECRET = os.getenv("META_APP_SECRET")
# #     META_REDIRECT_URI = os.getenv("META_REDIRECT_URI")

# #     WHATSAPP_VERIFY_TOKEN = os.getenv(
# #         "WHATSAPP_VERIFY_TOKEN"
# #     )

# #     WHATSAPP_ACCESS_TOKEN = os.getenv(
# #         "WHATSAPP_ACCESS_TOKEN"
# #     )

# #     WHATSAPP_PHONE_NUMBER_ID = os.getenv(
# #         "WHATSAPP_PHONE_NUMBER_ID"
# #     )

# #     LINKEDIN_CLIENT_ID = os.getenv(
# #         "LINKEDIN_CLIENT_ID"
# #     )

# #     LINKEDIN_CLIENT_SECRET = os.getenv(
# #         "LINKEDIN_CLIENT_SECRET"
# #     )

# #     LINKEDIN_REDIRECT_URI = os.getenv(
# #         "LINKEDIN_REDIRECT_URI"
# #     )

# # settings = Settings()