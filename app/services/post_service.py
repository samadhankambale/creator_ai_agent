from app.repositories.user_repository import (
    user_repository
)

from app.repositories.post_repository import (
    post_repository
)

from app.repositories.publish_job_repository import (
    publish_job_repository
)

from app.services.social_account_service import (
    social_account_service
)

from app.integrations.pollinations.image_client import (
    generate_image
)


class PostService:

    # =================================================
    # CREATE AI POST
    # =================================================

    async def create_ai_post(
        self,
        db,
        whatsapp_number,
        prompt
    ):

        # =============================================
        # GET OR CREATE USER
        # =============================================

        user = (
            social_account_service
            .get_or_create_user(

                db,

                whatsapp_number
            )
        )

        # =============================================
        # GENERATE CAPTION
        # =============================================

        caption = (

            f"🚀 {prompt}\n\n"
            f"Stay consistent and "
            f"keep growing every day.\n\n"
            f"#startup #motivation "
            f"#business #success"
        )

        # =============================================
        # GENERATE IMAGE
        # =============================================

        image_url = await generate_image(
            prompt
        )

        print("IMAGE URL:")
        print(image_url)

        # =============================================
        # SAVE POST
        # =============================================

        post = (
            post_repository
            .create_post(

                db=db,

                user_id=user.id,

                prompt=prompt,

                caption=caption,

                image_url=image_url
            )
        )

        # =============================================
        # RETURN
        # =============================================

        return {

            "post_id":
            post.id,

            "caption":
            caption,

            "image_url":
            image_url
        }

    # =================================================
    # CREATE IMMEDIATE JOBS
    # =================================================

    def create_immediate_publish_jobs(
        self,
        db,
        whatsapp_number,
        pending_post,
        platforms
    ):

        # =============================================
        # GET USER
        # =============================================

        user = (
            social_account_service
            .get_user_by_whatsapp(

                db,

                whatsapp_number
            )
        )

        if not user:

            raise Exception(
                "User not found"
            )

        jobs = []

        # =============================================
        # CREATE JOBS
        # =============================================

        for platform in platforms:

            job = (

                publish_job_repository
                .create_job(

                    db=db,

                    user_id=user.id,

                    post_id=
                    pending_post[
                        "post_id"
                    ],

                    platform=
                    platform,

                    scheduled_time=None
                )
            )

            jobs.append(job)

        return jobs

    # =================================================
    # CREATE SCHEDULED JOBS
    # =================================================

    def create_scheduled_publish_jobs(
        self,
        db,
        whatsapp_number,
        pending_post,
        platforms,
        scheduled_time
    ):

        # =============================================
        # GET USER
        # =============================================

        user = (
            social_account_service
            .get_user_by_whatsapp(

                db,

                whatsapp_number
            )
        )

        if not user:

            raise Exception(
                "User not found"
            )

        jobs = []

        # =============================================
        # CREATE JOBS
        # =============================================

        for platform in platforms:

            job = (

                publish_job_repository
                .create_job(

                    db=db,

                    user_id=user.id,

                    post_id=
                    pending_post[
                        "post_id"
                    ],

                    platform=
                    platform,

                    scheduled_time=
                    scheduled_time
                )
            )

            jobs.append(job)

        return jobs

    # =================================================
    # GET CONNECTED PLATFORMS
    # =================================================

    def get_connected_platforms(
        self,
        db,
        whatsapp_number
    ):

        return (

            social_account_service
            .get_connected_platforms(

                db=db,

                whatsapp_number=
                whatsapp_number
            )
        )

    # =================================================
    # GET MISSING PLATFORMS
    # =================================================

    

    def get_missing_platforms(
        self,
        db,
        whatsapp_number,
        platforms
    ):

        print("================================")
        print("CHECKING MISSING PLATFORMS")
        print("================================")

        print("WHATSAPP NUMBER:")
        print(whatsapp_number)

        print("PLATFORMS:")
        print(platforms)

        connected_platforms = (
            self.get_connected_platforms(
                db,
                whatsapp_number
            )
        )

        print("CONNECTED PLATFORMS:")
        print(connected_platforms)

        missing = []

        for platform in platforms:

            if platform not in connected_platforms:

                missing.append(platform)

        print("MISSING:")
        print(missing)

        return missing
    
post_service = (
    PostService()
)