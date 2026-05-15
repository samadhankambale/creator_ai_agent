from app.integrations.instagram.instagram_client import (
    post_to_instagram
)

from app.integrations.linkedin.linkedin_client import (
    post_to_linkedin
)

from app.integrations.twitter.twitter_client import (
    post_to_twitter
)

from app.integrations.facebook.facebook_client import (
    post_to_facebook
)


class PublishingService:

    # ==================================================
    # MAIN PUBLISH
    # ==================================================

    def publish_post(
        self,
        platform,
        caption,
        image_url,
        account
    ):

        # ----------------------------------------------
        # INSTAGRAM
        # ----------------------------------------------

        if platform == "instagram":

            return post_to_instagram(

                image_url=image_url,

                caption=caption,

                access_token=
                account.access_token,

                instagram_user_id=
                account.platform_user_id
            )

        # ----------------------------------------------
        # LINKEDIN
        # ----------------------------------------------

        if platform == "linkedin":

            return post_to_linkedin(

                caption=caption,

                image_url=image_url,

                access_token=
                account.access_token,

                linkedin_user_id=
                account.platform_user_id
            )

        # ----------------------------------------------
        # TWITTER
        # ----------------------------------------------

        if platform == "twitter":

            return post_to_twitter(

                caption=caption,

                image_url=image_url,

                access_token=
                account.access_token,

                twitter_user_id=
                account.platform_user_id
            )

        # ----------------------------------------------
        # FACEBOOK
        # ----------------------------------------------

        if platform == "facebook":

            return post_to_facebook(

                caption=caption,

                image_url=image_url,

                access_token=
                account.access_token,

                facebook_page_id=
                account.platform_user_id
            )

        raise Exception(
            f"Unsupported platform: {platform}"
        )


publishing_service = (
    PublishingService()
)