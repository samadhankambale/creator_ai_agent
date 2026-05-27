from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY not set in .env")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> str:
    if not token:
        return token
    try:
        return _get_fernet().encrypt(token.encode()).decode()
    except Exception as e:
        print(f"ENCRYPT ERROR: {e}")
        return token


def decrypt_token(token: str) -> str:
    if not token:
        return token
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return token  # legacy unencrypted token — return as-is