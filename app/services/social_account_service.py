from sqlalchemy.orm import Session
from app.models.user_social_account import UserSocialAccount
from app.models.user import User
from app.core.encryption import encrypt_token, decrypt_token


class SocialAccountService:

    def upsert(
        self,
        db: Session,
        user_id,
        platform: str,
        access_token: str,
        platform_user_id: str,
        username: str = "",
    ) -> UserSocialAccount:
        """Create or update a social account connection."""
        account = (
            db.query(UserSocialAccount)
            .filter(
                UserSocialAccount.user_id == user_id,
                UserSocialAccount.platform_type == platform,
            )
            .first()
        )

        encrypted = encrypt_token(access_token)

        if account:
            account.access_token = encrypted
            account.api_key = platform_user_id
            account.username = username
            account.is_active = True
        else:
            account = UserSocialAccount(
                user_id=user_id,
                platform_type=platform,
                access_token=encrypted,
                api_key=platform_user_id,
                username=username,
                is_active=True,
            )
            db.add(account)

        db.commit()
        db.refresh(account)
        print(f"SOCIAL ACCOUNT SAVED: {platform} for user {user_id}")
        return account

    def get(self, db: Session, user_id, platform: str) -> UserSocialAccount | None:
        return (
            db.query(UserSocialAccount)
            .filter(
                UserSocialAccount.user_id == user_id,
                UserSocialAccount.platform_type == platform,
                UserSocialAccount.is_active == True,
            )
            .first()
        )

    def get_decrypted(self, db: Session, user_id, platform: str):
        """Return account with decrypted access token."""
        account = self.get(db, user_id, platform)
        if not account:
            return None

        try:
            decrypted = decrypt_token(account.access_token)
        except Exception:
            decrypted = account.access_token  # fallback for unencrypted

        # Return a simple object with decrypted token
        class DecryptedAccount:
            def __init__(self, acc, token):
                self.platform_type = acc.platform_type
                self.platform_user_id = acc.api_key
                self.username = acc.username
                self.access_token = token

        return DecryptedAccount(account, decrypted)

    def get_missing_platforms(
        self,
        db: Session,
        whatsapp_number: str,
        platforms: list,
    ) -> list:
        """Return platforms from list that are not connected."""
        user = db.query(User).filter(User.number == whatsapp_number).first()
        if not user:
            return platforms
        return [
            p for p in platforms
            if not self.get(db, user.id, p)
        ]


social_account_service = SocialAccountService()