from cryptography.fernet import (
    Fernet
)

from app.core.config import (
    settings
)


cipher = Fernet(

    settings.ENCRYPTION_KEY.encode()
)


# =====================================================
# ENCRYPT TOKEN
# =====================================================

def encrypt_token(
    token: str
):

    encrypted = cipher.encrypt(

        token.encode()
    )

    return encrypted.decode()


# =====================================================
# DECRYPT TOKEN
# =====================================================

def decrypt_token(
    encrypted_token: str
):

    decrypted = cipher.decrypt(

        encrypted_token.encode()
    )

    return decrypted.decode()