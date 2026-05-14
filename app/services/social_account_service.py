from sqlalchemy.orm import Session

from app.repositories.user_repository import (
    user_repository
)

from app.repositories.social_account_repository import (
    social_account_repository
)


class SocialAccountService:

    # ==================================================
    # GET OR CREATE USER
    # ==================================================

    def get_or_create_user(
        self,
        db: Session,
        whatsapp_number: str,
        full_name: str = None
    ):

        user = (
            user_repository
            .get_by_whatsapp_number(
                db,
                whatsapp_number
            )
        )

        # ----------------------------------------------
        # RETURN EXISTING USER
        # ----------------------------------------------

        if user:

            return user

        # ----------------------------------------------
        # CREATE NEW USER
        # ----------------------------------------------

        user = (
            user_repository
            .create_user(
                db,
                whatsapp_number,
                full_name
            )
        )

        return user

    # ==================================================
    # CONNECT PLATFORM ACCOUNT
    # ==================================================

    def connect_platform_account(
        self,
        db: Session,
        whatsapp_number: str,
        platform: str,
        access_token: str,
        refresh_token: str = None,
        platform_user_id: str = None,
        username: str = None
    ):

        # ----------------------------------------------
        # GET OR CREATE USER
        # ----------------------------------------------

        user = self.get_or_create_user(
            db,
            whatsapp_number
        )

        # ----------------------------------------------
        # CREATE/UPDATE ACCOUNT
        # ----------------------------------------------

        account = (
            social_account_repository
            .create_account(
                db=db,

                user_id=user.id,

                platform=platform,

                access_token=access_token,

                refresh_token=refresh_token,

                platform_user_id=
                platform_user_id,

                username=username
            )
        )

        return account

    # ==================================================
    # GET CONNECTED ACCOUNT
    # ==================================================

    def get_connected_account(
        self,
        db: Session,
        whatsapp_number: str,
        platform: str
    ):

        # ----------------------------------------------
        # FIND USER
        # ----------------------------------------------

        user = (
            user_repository
            .get_by_whatsapp_number(
                db,
                whatsapp_number
            )
        )

        if not user:

            return None

        # ----------------------------------------------
        # GET DECRYPTED ACCOUNT
        # ----------------------------------------------

        account = (
            social_account_repository
            .get_decrypted_account(
                db,
                user.id,
                platform
            )
        )

        return account

    # ==================================================
    # GET ALL CONNECTED ACCOUNTS
    # ==================================================

    def get_all_connected_accounts(
        self,
        db: Session,
        whatsapp_number: str
    ):

        # ----------------------------------------------
        # FIND USER
        # ----------------------------------------------

        user = (
            user_repository
            .get_by_whatsapp_number(
                db,
                whatsapp_number
            )
        )

        if not user:

            return []

        accounts = (
            social_account_repository
            .get_all_user_accounts(
                db,
                user.id
            )
        )

        # ----------------------------------------------
        # DECRYPT TOKENS
        # ----------------------------------------------

        decrypted_accounts = []

        for account in accounts:

            decrypted_account = (
                social_account_repository
                .get_decrypted_account(
                    db,
                    user.id,
                    account.platform
                )
            )

            decrypted_accounts.append(
                decrypted_account
            )

        return decrypted_accounts

    # ==================================================
    # CHECK PLATFORM CONNECTED
    # ==================================================

    def is_platform_connected(
        self,
        db: Session,
        whatsapp_number: str,
        platform: str
    ):

        account = (
            self.get_connected_account(
                db,
                whatsapp_number,
                platform
            )
        )

        return account is not None

    # ==================================================
    # DISCONNECT PLATFORM
    # ==================================================

    def disconnect_platform(
        self,
        db: Session,
        whatsapp_number: str,
        platform: str
    ):

        user = (
            user_repository
            .get_by_whatsapp_number(
                db,
                whatsapp_number
            )
        )

        if not user:

            return None

        account = (
            social_account_repository
            .disconnect_account(
                db,
                user.id,
                platform
            )
        )

        return account

    # ==================================================
    # GET USER BY WHATSAPP
    # ==================================================

    def get_user_by_whatsapp(
        self,
        db: Session,
        whatsapp_number: str
    ):

        return (
            user_repository
            .get_by_whatsapp_number(
                db,
                whatsapp_number
            )
        )


social_account_service = (
    SocialAccountService()
)