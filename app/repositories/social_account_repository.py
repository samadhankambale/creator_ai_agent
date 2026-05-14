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

        existing_account = (

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

        # ----------------------------------------------
        # UPDATE EXISTING ACCOUNT
        # ----------------------------------------------

        if existing_account:

            existing_account.access_token = (
                encrypt_token(
                    access_token
                )
            )

            existing_account.refresh_token = (

                encrypt_token(
                    refresh_token
                )

                if refresh_token
                else None
            )

            existing_account.platform_user_id = (
                platform_user_id
            )

            existing_account.username = (
                username
            )

            existing_account.is_active = True

            db.commit()

            db.refresh(existing_account)

            return existing_account

        # ----------------------------------------------
        # CREATE NEW ACCOUNT
        # ----------------------------------------------

        account = SocialAccount(

            user_id=user_id,

            platform=platform,

            access_token=
            encrypt_token(
                access_token
            ),

            refresh_token=(

                encrypt_token(
                    refresh_token
                )

                if refresh_token
                else None
            ),

            platform_user_id=
            platform_user_id,

            username=username
        )

        db.add(account)

        db.commit()

        db.refresh(account)

        return account

    # ==================================================
    # GET SINGLE ACCOUNT
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

            .filter(
                SocialAccount.is_active
                == True
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

            .filter(
                SocialAccount.is_active
                == True
            )

            .all()
        )

    # ==================================================
    # GET DECRYPTED ACCOUNT
    # ==================================================

    def get_decrypted_account(
        self,
        db: Session,
        user_id: int,
        platform: str
    ):

        account = (

            self.get_user_platform_account(
                db,
                user_id,
                platform
            )
        )

        if not account:

            return None

        account.access_token = (
            decrypt_token(
                account.access_token
            )
        )

        if account.refresh_token:

            account.refresh_token = (
                decrypt_token(
                    account.refresh_token
                )
            )

        return account

    # ==================================================
    # DISCONNECT ACCOUNT
    # ==================================================

    def disconnect_account(
        self,
        db: Session,
        user_id: int,
        platform: str
    ):

        account = (

            self.get_user_platform_account(
                db,
                user_id,
                platform
            )
        )

        if not account:

            return None

        account.is_active = False

        db.commit()

        db.refresh(account)

        return account


social_account_repository = (
    SocialAccountRepository()
)