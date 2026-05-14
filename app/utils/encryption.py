from cryptography.fernet import (
    Fernet
)

from app.core.config import settings


cipher = Fernet(

    settings.ENCRYPTION_KEY.encode()
)


def encrypt_token(
    token: str
):

    encrypted = cipher.encrypt(
        token.encode()
    )

    return encrypted.decode()


def decrypt_token(
    encrypted_token: str
):

    decrypted = cipher.decrypt(
        encrypted_token.encode()
    )

    return decrypted.decode()