from sqlalchemy.orm import Session
from app.repositories.user_repository import user_repository
from app.repositories.social_account_repository import social_account_repository


class SocialAccountService:

    def connect_platform_account(
        self,
        db: Session,
        whatsapp_number: str,
        platform: str,
        access_token: str,
        platform_user_id: str,
        username: str,
    ):
        user = user_repository.get_or_create(db, whatsapp_number)
        account = social_account_repository.upsert(
            db=db,
            user_id=user.id,
            platform=platform,
            access_token=access_token,
            platform_user_id=platform_user_id,
            username=username,
        )
        print(f"SOCIAL ACCOUNT SAVED: {platform} for {whatsapp_number}")
        return account

    def get_missing_platforms(
        self,
        db: Session,
        whatsapp_number: str,
        platforms: list,
    ) -> list:
        """Return platforms from the list that are not yet connected."""
        user = user_repository.get_by_whatsapp(db, whatsapp_number)
        if not user:
            return platforms
        return [
            p for p in platforms
            if not social_account_repository.get(db, user.id, p)
        ]


social_account_service = SocialAccountService()