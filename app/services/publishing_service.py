from app.integrations.instagram.instagram_client import post_to_instagram
from app.integrations.linkedin.linkedin_client import post_to_linkedin
from app.integrations.threads.threads_client import post_to_threads
from app.integrations.twitter.twitter_client import post_to_twitter

CAROUSEL_SUPPORTED = ["instagram", "linkedin", "threads"]
VIDEO_SUPPORTED = ["instagram", "linkedin", "threads"]
REELS_SUPPORTED = ["instagram"]
STORIES_SUPPORTED = ["instagram"]


class PublishingService:

    def publish(
        self,
        platform: str,
        access_token: str,
        platform_user_id: str,
        caption: str,
        image_url: str,
        extra_image_urls: list = None,
        video_url: str = None,
        post_type: str = "post",  # post | reel | story
    ) -> dict:

        print("=" * 40)
        print(f"PUBLISHING TO: {platform}")
        print(f"POST TYPE: {post_type}")
        print(f"IMAGES: {1 + len(extra_image_urls or [])}")
        print(f"VIDEO: {bool(video_url)}")
        print(f"PLATFORM USER ID: {platform_user_id}")
        print("=" * 40)

        # Reel — Instagram only
        if post_type == "reel" and platform not in REELS_SUPPORTED:
            return {
                "success": False,
                "error": f"{platform.title()} doesn't support Reels",
                "details": f"Reels only supported on Instagram",
            }

        # Story — Instagram only
        if post_type == "story" and platform not in STORIES_SUPPORTED:
            return {
                "success": False,
                "error": f"{platform.title()} doesn't support Stories",
                "details": f"Stories only supported on Instagram",
            }

        # LinkedIn video not supported
        if video_url and platform == "linkedin":
            return {
                "success": False,
                "error": "LinkedIn video not supported",
                "details": "LinkedIn video upload requires chunked upload API — not implemented yet.",
                "skip_reconnect": True,
            }

        # Carousel not supported
        if extra_image_urls and platform not in CAROUSEL_SUPPORTED:
            print(f"{platform}: carousel not supported, posting first image only")

        if platform == "instagram":
            return post_to_instagram(
                access_token=access_token,
                platform_user_id=platform_user_id,
                image_url=image_url,
                caption=caption,
                extra_image_urls=extra_image_urls if platform in CAROUSEL_SUPPORTED else None,
                post_type=post_type,
                video_url=video_url,
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
                video_url=video_url,
            )

        elif platform == "twitter":
            return post_to_twitter(
                access_token=access_token,
                twitter_user_id=platform_user_id,
                caption=caption,
                image_url=image_url,
            )

        return {"success": False, "error": f"Platform '{platform}' not supported"}


publishing_service = PublishingService()