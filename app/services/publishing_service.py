from app.integrations.instagram.instagram_client import (
    post_to_instagram
)

from app.integrations.linkedin.linkedin_client import (
    post_to_linkedin
)


class PublishingService:

    # =================================================
    # MAIN PUBLISH METHOD
    # =================================================

    def publish_post(
        self,
        platform,
        caption,
        image_url,
        account
    ):

        print("================================")
        print("PUBLISHING SERVICE")
        print("================================")

        print("PLATFORM:")
        print(platform)

        print("CAPTION:")
        print(caption)

        print("IMAGE URL:")
        print(image_url)

        print("ACCOUNT:")
        print(account)

        # =============================================
        # INSTAGRAM
        # =============================================

        if platform == "instagram":

            print(
                "STARTING INSTAGRAM PUBLISH"
            )

            result = (
                post_to_instagram(

                    access_token=
                    account.access_token,

                    account_id=
                    account.platform_user_id,

                    caption=
                    caption,

                    image_url=
                    image_url
                )
            )

            print(
                "INSTAGRAM RESULT:"
            )

            print(result)

            return result

        # =============================================
        # LINKEDIN
        # =============================================

        elif platform == "linkedin":

            print(
                "STARTING LINKEDIN PUBLISH"
            )

            result = (
                post_to_linkedin(

                    access_token=
                    account.access_token,

                    person_id=
                    account.platform_user_id,

                    caption=
                    caption,

                    image_url=
                    image_url
                )
            )

            print(
                "LINKEDIN RESULT:"
            )

            print(result)

            return result

        # =============================================
        # FACEBOOK
        # =============================================

        elif platform == "facebook":

            print(
                "FACEBOOK NOT IMPLEMENTED"
            )

            return {

                "success":
                False,

                "error":
                (
                    "Facebook publishing "
                    "not implemented yet"
                )
            }

        # =============================================
        # TWITTER
        # =============================================

        elif platform == "twitter":

            print(
                "TWITTER NOT IMPLEMENTED"
            )

            return {

                "success":
                False,

                "error":
                (
                    "Twitter publishing "
                    "not implemented yet"
                )
            }

        # =============================================
        # INVALID PLATFORM
        # =============================================

        return {

            "success":
            False,

            "error":
            f"{platform} not supported"
        }


publishing_service = (
    PublishingService()
)