from copy import deepcopy

from sqlalchemy.orm import Session

from app.models.social_account import (
    SocialAccount
)

from app.utils.encryption import (
    encrypt_token,
    decrypt_token
)


class SocialAccountRepository:

    # ==================================================
    # CREATE ACCOUNT
    # ==================================================

    def create_account(
        self,
        db: Session,
        user_id: int,
        platform: str,
        access_token: str,
        refresh_token: str = None,
        platform_user_id: str = None,
        username: str = None
    ):

        encrypted_access_token = (
            encrypt_token(access_token)
        )

        account = SocialAccount(

            user_id=user_id,

            platform=platform,

            access_token=
            encrypted_access_token,

            refresh_token=
            refresh_token,

            platform_user_id=
            platform_user_id,

            username=username
        )

        db.add(account)

        db.commit()

        db.refresh(account)

        return account

    # ==================================================
    # GET USER PLATFORM ACCOUNT
    # ==================================================

    def get_user_platform_account(
        self,
        db: Session,
        user_id: int,
        platform: str
    ):

        return (

            db.query(SocialAccount)

            .filter(
                SocialAccount.user_id
                == user_id
            )

            .filter(
                SocialAccount.platform
                == platform
            )

            .first()
        )

    # ==================================================
    # GET ALL USER ACCOUNTS
    # ==================================================

    def get_all_user_accounts(
        self,
        db: Session,
        user_id: int
    ):

        return (

            db.query(SocialAccount)

            .filter(
                SocialAccount.user_id
                == user_id
            )

            .all()
        )

    # ==================================================
    # SAFE DECRYPT
    # ==================================================

    def get_decrypted_account(
        self,
        account
    ):

        safe_account = deepcopy(
            account
        )

        token = safe_account.access_token

        # already decrypted
        if token.startswith("EAAX"):

            return safe_account

        safe_account.access_token = (

            decrypt_token(token)
        )

        return safe_account


social_account_repository = (
    SocialAccountRepository()
)