from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    DATABASE_URL: str
    REDIS_URL: str
    ENCRYPTION_KEY: str

    GROQ_API_KEY: str

    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str

    # ── Instagram / Facebook ──────────────────────────
    META_APP_ID: str
    META_APP_SECRET: str
    META_REDIRECT_URI: str

    # ── Threads (separate app on Meta) ───────────────
    THREADS_APP_ID: str = ""
    THREADS_APP_SECRET: str = ""
    THREADS_REDIRECT_URI: str = ""

    # ── LinkedIn ──────────────────────────────────────
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = ""

    APP_BASE_URL: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )


settings = Settings()