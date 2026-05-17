from app.models.social_account import (
    SocialAccount
)

from app.repositories.user_repository import (
    user_repository
)

from app.repositories.social_account_repository import (
    social_account_repository
)


class SocialAccountService:

    # ==================================================
    # GET USER BY WHATSAPP
    # ==================================================

    def get_user_by_whatsapp(
        self,
        db,
        whatsapp_number
    ):

        return (
            user_repository
            .get_user_by_whatsapp(
                db,
                whatsapp_number
            )
        )

    # ==================================================
    # CREATE USER
    # ==================================================

    def create_user(
        self,
        db,
        whatsapp_number
    ):

        return (
            user_repository
            .create_user(
                db,
                whatsapp_number
            )
        )

    # ==================================================
    # GET OR CREATE USER
    # ==================================================

    def get_or_create_user(
        self,
        db,
        whatsapp_number
    ):

        user = (
            self.get_user_by_whatsapp(
                db,
                whatsapp_number
            )
        )

        if user:

            return user

        return (
            self.create_user(
                db,
                whatsapp_number
            )
        )

    # ==================================================
    # CONNECT PLATFORM ACCOUNT
    # ==================================================

    def connect_platform_account(
        self,
        db,
        whatsapp_number,
        platform,
        access_token,
        refresh_token=None,
        platform_user_id=None,
        username=None
    ):

        user = (
            self.get_or_create_user(
                db,
                whatsapp_number
            )
        )

        # ----------------------------------------------
        # REMOVE OLD ACCOUNT
        # ----------------------------------------------

        existing = (

            db.query(SocialAccount)

            .filter(
                SocialAccount.user_id
                == user.id
            )

            .filter(
                SocialAccount.platform
                == platform
            )

            .first()
        )

        if existing:

            db.delete(existing)

            db.commit()

        # ----------------------------------------------
        # CREATE NEW ACCOUNT
        # ----------------------------------------------

        account = (

            social_account_repository
            .create_account(

                db=db,

                user_id=user.id,

                platform=platform,

                access_token=
                access_token,

                refresh_token=
                refresh_token,

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
        db,
        whatsapp_number,
        platform
    ):

        user = (
            self.get_user_by_whatsapp(
                db,
                whatsapp_number
            )
        )

        if not user:

            return None

        account = (

            social_account_repository
            .get_user_platform_account(

                db=db,

                user_id=user.id,

                platform=platform
            )
        )

        if not account:

            return None

        decrypted_account = (

            social_account_repository
            .get_decrypted_account(
                account
            )
        )

        return decrypted_account

    # ==================================================
    # GET ALL CONNECTED ACCOUNTS
    # ==================================================

    def get_all_connected_accounts(
        self,
        db,
        whatsapp_number
    ):

        user = (
            self.get_user_by_whatsapp(
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

        decrypted_accounts = []

        for account in accounts:

            decrypted = (

                social_account_repository
                .get_decrypted_account(
                    account
                )
            )

            decrypted_accounts.append(
                decrypted
            )

        return decrypted_accounts

    # ==================================================
    # IS PLATFORM CONNECTED
    # ==================================================

    def is_platform_connected(
        self,
        db,
        whatsapp_number,
        platform
    ):

        account = (
            self.get_connected_account(

                db=db,

                whatsapp_number=
                whatsapp_number,

                platform=platform
            )
        )

        return account is not None

    # ==================================================
    # GET CONNECTED PLATFORMS
    # ==================================================

    def get_connected_platforms(
        self,
        db,
        whatsapp_number
    ):

        accounts = (
            self.get_all_connected_accounts(

                db=db,

                whatsapp_number=
                whatsapp_number
            )
        )

        platforms = []

        for account in accounts:

            platforms.append(
                account.platform
            )

        return platforms


social_account_service = (
    SocialAccountService()
)