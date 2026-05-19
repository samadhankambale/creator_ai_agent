from app.integrations.instagram.instagram_client import post_to_instagram
from app.integrations.linkedin.linkedin_client import post_to_linkedin
from app.integrations.threads.threads_client import post_to_threads


class PublishingService:

    def publish(
        self,
        platform: str,
        access_token: str,
        platform_user_id: str,
        caption: str,
        image_url: str,
    ) -> dict:

        print("=" * 40)
        print(f"PUBLISHING TO: {platform}")
        print(f"PLATFORM USER ID: {platform_user_id}")
        print(f"CAPTION: {caption[:60]}...")
        print("=" * 40)

        if platform == "instagram":
            return post_to_instagram(
                access_token=access_token,
                platform_user_id=platform_user_id,
                image_url=image_url,
                caption=caption,
            )

        elif platform == "linkedin":
            return post_to_linkedin(
                access_token=access_token,
                person_id=platform_user_id,
                caption=caption,
                image_url=image_url,
            )

        elif platform == "threads":
            return post_to_threads(
                access_token=access_token,
                threads_user_id=platform_user_id,
                caption=caption,
                image_url=image_url,
            )

        return {
            "success": False,
            "error": f"Platform '{platform}' not supported",
        }


publishing_service = PublishingService()