from app.integrations.instagram.instagram_client import post_to_instagram
from app.integrations.linkedin.linkedin_client import post_to_linkedin
from app.integrations.threads.threads_client import post_to_threads
from app.integrations.twitter.twitter_client import post_to_twitter

# Platforms that support carousel/multiple images
CAROUSEL_SUPPORTED = ["instagram", "linkedin", "threads"]


class PublishingService:

    def publish(
        self,
        platform: str,
        access_token: str,
        platform_user_id: str,
        caption: str,
        image_url: str,
        extra_image_urls: list = None,
    ) -> dict:

        has_multiple = extra_image_urls and len(extra_image_urls) > 0
        total_images = 1 + len(extra_image_urls or [])

        print("=" * 40)
        print(f"PUBLISHING TO: {platform}")
        print(f"IMAGES: {total_images}")
        print(f"PLATFORM USER ID: {platform_user_id}")
        print("=" * 40)

        # Warn if platform doesn't support carousel
        if has_multiple and platform not in CAROUSEL_SUPPORTED:
            print(f"{platform}: carousel not supported, posting first image only")

        if platform == "instagram":
            return post_to_instagram(
                access_token=access_token,
                platform_user_id=platform_user_id,
                image_url=image_url,
                caption=caption,
                extra_image_urls=extra_image_urls if platform in CAROUSEL_SUPPORTED else None,
            )

        elif platform == "linkedin":
            return post_to_linkedin(
                access_token=access_token,
                person_id=platform_user_id,
                caption=caption,
                image_url=image_url,
                extra_image_urls=extra_image_urls if platform in CAROUSEL_SUPPORTED else None,
            )

        elif platform == "threads":
            return post_to_threads(
                access_token=access_token,
                threads_user_id=platform_user_id,
                caption=caption,
                image_url=image_url,
                extra_image_urls=extra_image_urls if platform in CAROUSEL_SUPPORTED else None,
            )

        elif platform == "twitter":
            # Twitter: single image only
            return post_to_twitter(
                access_token=access_token,
                twitter_user_id=platform_user_id,
                caption=caption,
                image_url=image_url,
            )

        return {
            "success": False,
            "error": f"Platform '{platform}' not supported",
        }


publishing_service = PublishingService()