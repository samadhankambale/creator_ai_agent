from sqlalchemy.orm import Session

from app.integrations.groq.groq_client import (
    generate_caption
)

from app.integrations.pollinations.image_client import (
    generate_image
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

from app.utils.datetime_parser import (
    parse_schedule_datetime,
    is_schedule_request
)


class PostService:

    # ==================================================
    # CREATE AI POST
    # ==================================================

    async def create_ai_post(
        self,
        db: Session,
        whatsapp_number: str,
        prompt: str
    ):

        # ----------------------------------------------
        # GET OR CREATE USER
        # ----------------------------------------------

        user = (
            social_account_service
            .get_or_create_user(
                db,
                whatsapp_number
            )
        )

        # ----------------------------------------------
        # GENERATE CAPTION
        # ----------------------------------------------

        caption = await generate_caption(
            prompt
        )

        # ----------------------------------------------
        # GENERATE IMAGE
        # ----------------------------------------------

        image_url = await generate_image(
            caption
        )

        # ----------------------------------------------
        # DETECT SCHEDULE
        # ----------------------------------------------

        scheduled_time = None

        if is_schedule_request(prompt):

            scheduled_time = (
                parse_schedule_datetime(
                    prompt,
                    user.timezone
                )
            )

        # ----------------------------------------------
        # CREATE POST
        # ----------------------------------------------

        post = (
            post_repository
            .create_post(

                db=db,

                user_id=user.id,

                prompt=prompt,

                caption=caption,

                image_url=image_url,

                status=(

                    "scheduled"

                    if scheduled_time

                    else "draft"
                )
            )
        )

        # ----------------------------------------------
        # SAVE SCHEDULE TIME
        # ----------------------------------------------

        if scheduled_time:

            post.scheduled_time = (
                scheduled_time
            )

            db.commit()

            db.refresh(post)

        return {

            "post_id":
            post.id,

            "caption":
            caption,

            "image_url":
            image_url,

            "scheduled_time":
            scheduled_time
        }

    # ==================================================
    # CREATE PUBLISH JOBS
    # ==================================================

    def create_publish_jobs(
        self,
        db: Session,
        user_id: int,
        post_id: int,
        platforms: list,
        scheduled_time = None
    ):

        jobs = []

        for platform in platforms:

            job = (
                publish_job_repository
                .create_job(

                    db=db,

                    user_id=user_id,

                    post_id=post_id,

                    platform=platform,

                    scheduled_time=
                    scheduled_time
                )
            )

            jobs.append(job)

        return jobs

    # ==================================================
    # GET USER CONNECTED PLATFORMS
    # ==================================================

    def get_connected_platforms(
        self,
        db: Session,
        whatsapp_number: str
    ):

        accounts = (
            social_account_service
            .get_all_connected_accounts(
                db,
                whatsapp_number
            )
        )

        return [

            account.platform

            for account in accounts
        ]

    # ==================================================
    # GET MISSING PLATFORMS
    # ==================================================

    def get_missing_platforms(
        self,
        db: Session,
        whatsapp_number: str,
        requested_platforms: list
    ):

        connected_platforms = (
            self.get_connected_platforms(
                db,
                whatsapp_number
            )
        )

        missing_platforms = []

        for platform in requested_platforms:

            if platform not in connected_platforms:

                missing_platforms.append(
                    platform
                )

        return missing_platforms

    # ==================================================
    # CREATE IMMEDIATE PUBLISH
    # ==================================================

    def create_immediate_publish_jobs(
        self,
        db: Session,
        whatsapp_number: str,
        post_id: int,
        platforms: list
    ):

        user = (
            social_account_service
            .get_user_by_whatsapp(
                db,
                whatsapp_number
            )
        )

        if not user:

            return []

        jobs = (
            self.create_publish_jobs(

                db=db,

                user_id=user.id,

                post_id=post_id,

                platforms=platforms,

                scheduled_time=None
            )
        )

        return jobs

    # ==================================================
    # CREATE SCHEDULED PUBLISH
    # ==================================================

    def create_scheduled_publish_jobs(
        self,
        db: Session,
        whatsapp_number: str,
        post_id: int,
        platforms: list,
        scheduled_time
    ):

        user = (
            social_account_service
            .get_user_by_whatsapp(
                db,
                whatsapp_number
            )
        )

        if not user:

            return []

        jobs = (
            self.create_publish_jobs(

                db=db,

                user_id=user.id,

                post_id=post_id,

                platforms=platforms,

                scheduled_time=
                scheduled_time
            )
        )

        return jobs


post_service = PostService()