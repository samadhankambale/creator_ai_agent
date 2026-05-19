from sqlalchemy.orm import Session
from app.models.social_account import SocialAccount
from app.utils.encryption import encrypt_token, decrypt_token


class SocialAccountRepository:

    def upsert(
        self,
        db: Session,
        user_id: int,
        platform: str,
        access_token: str,
        platform_user_id: str = None,
        username: str = None,
    ) -> SocialAccount:

        encrypted = encrypt_token(access_token)

        account = (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
            )
            .first()
        )

        if account:
            account.access_token = encrypted
            account.platform_user_id = platform_user_id
            account.username = username
            account.is_active = True
        else:
            account = SocialAccount(
                user_id=user_id,
                platform=platform,
                access_token=encrypted,
                platform_user_id=platform_user_id,
                username=username,
            )
            db.add(account)

        db.commit()
        db.refresh(account)
        return account

    def create_account(
        self,
        db: Session,
        user_id: int,
        platform: str,
        access_token: str,
        refresh_token: str = None,
        platform_user_id: str = None,
        username: str = None,
    ) -> SocialAccount:
        return self.upsert(
            db=db,
            user_id=user_id,
            platform=platform,
            access_token=access_token,
            platform_user_id=platform_user_id,
            username=username,
        )

    def get(
        self,
        db: Session,
        user_id: int,
        platform: str,
    ) -> SocialAccount:
        return (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == platform,
                SocialAccount.is_active == True,
            )
            .first()
        )

    def get_user_platform_account(self, db, user_id, platform):
        return self.get(db, user_id, platform)

    def _safe_decrypt(self, token: str) -> str:
        """
        Try to decrypt the token. If it fails (token was stored
        unencrypted in DB from an older code version), return it as-is.
        Also re-saves it properly encrypted so future calls work.
        """
        try:
            return decrypt_token(token)
        except Exception:
            print(
                "WARNING: token decryption failed — "
                "token appears to be stored unencrypted. Using as-is."
            )
            return token

    def get_decrypted(
        self,
        db: Session,
        user_id: int,
        platform: str,
    ):
        """
        Returns a plain detached object with a decrypted access_token.
        Never mutates the SQLAlchemy instance to avoid identity-map bugs.
        """
        account = self.get(db, user_id, platform)
        if not account:
            return None

        decrypted_token = self._safe_decrypt(account.access_token)

        class AccountData:
            pass

        result = AccountData()
        result.id = account.id
        result.user_id = account.user_id
        result.platform = account.platform
        result.username = account.username
        result.platform_user_id = account.platform_user_id
        result.is_active = account.is_active
        result.access_token = decrypted_token

        return result

    def get_all_user_accounts(self, db, user_id):
        return (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user_id)
            .all()
        )


social_account_repository = SocialAccountRepository()