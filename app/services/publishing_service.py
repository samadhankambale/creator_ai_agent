from datetime import datetime

from sqlalchemy.orm import Session

from app.integrations.instagram.instagram_client import (
    post_to_instagram
)

from app.integrations.linkedin.linkedin_client import (
    post_to_linkedin
)

from app.integrations.twitter.twitter_client import (
    post_to_twitter
)

from app.repositories.post_repository import (
    post_repository
)

from app.repositories.publish_job_repository import (
    publish_job_repository
)


class PublishingService:

    # ==================================================
    # MAIN PUBLISH METHOD
    # ==================================================

    def publish_post(
        self,
        platform: str,
        caption: str,
        image_url: str,
        account
    ):

        # ----------------------------------------------
        # INSTAGRAM
        # ----------------------------------------------

        if platform == "instagram":

            return self.publish_to_instagram(

                caption=caption,

                image_url=image_url,

                account=account
            )

        # ----------------------------------------------
        # LINKEDIN
        # ----------------------------------------------

        if platform == "linkedin":

            return self.publish_to_linkedin(

                caption=caption,

                image_url=image_url,

                account=account
            )

        # ----------------------------------------------
        # TWITTER
        # ----------------------------------------------

        if platform == "twitter":

            return self.publish_to_twitter(

                caption=caption,

                image_url=image_url,

                account=account
            )

        # ----------------------------------------------
        # UNSUPPORTED
        # ----------------------------------------------

        raise Exception(
            f"Unsupported platform: {platform}"
        )

    # ==================================================
    # INSTAGRAM PUBLISH
    # ==================================================

    def publish_to_instagram(
        self,
        caption: str,
        image_url: str,
        account
    ):

        print("POSTING TO INSTAGRAM")

        result = post_to_instagram(

            image_url=image_url,

            caption=caption,

            access_token=
            account.access_token,

            instagram_user_id=
            account.platform_user_id
        )

        print("INSTAGRAM RESULT:")
        print(result)

        return result

    # ==================================================
    # LINKEDIN PUBLISH
    # ==================================================

    def publish_to_linkedin(
        self,
        caption: str,
        image_url: str,
        account
    ):

        print("POSTING TO LINKEDIN")

        result = post_to_linkedin(

            caption=caption,

            image_url=image_url,

            access_token=
            account.access_token,

            linkedin_user_id=
            account.platform_user_id
        )

        print("LINKEDIN RESULT:")
        print(result)

        return result

    # ==================================================
    # TWITTER PUBLISH
    # ==================================================

    def publish_to_twitter(
        self,
        caption: str,
        image_url: str,
        account
    ):

        print("POSTING TO TWITTER")

        result = post_to_twitter(

            caption=caption,

            image_url=image_url,

            access_token=
            account.access_token,

            twitter_user_id=
            account.platform_user_id
        )

        print("TWITTER RESULT:")
        print(result)

        return result

    # ==================================================
    # MARK JOB SUCCESS
    # ==================================================

    def mark_job_success(
        self,
        db: Session,
        job_id: int,
        post_id: int
    ):

        publish_job_repository.update_job_status(

            db=db,

            job_id=job_id,

            status="success"
        )

        post_repository.update_post_status(

            db=db,

            post_id=post_id,

            status="published"
        )

    # ==================================================
    # MARK JOB FAILED
    # ==================================================

    def mark_job_failed(
        self,
        db: Session,
        job_id: int,
        error_message: str
    ):

        publish_job_repository.update_job_status(

            db=db,

            job_id=job_id,

            status="failed",

            error_message=
            error_message
        )

    # ==================================================
    # MARK JOB PROCESSING
    # ==================================================

    def mark_job_processing(
        self,
        db: Session,
        job_id: int
    ):

        publish_job_repository.update_job_status(

            db=db,

            job_id=job_id,

            status="processing"
        )

    # ==================================================
    # COMPLETE JOB
    # ==================================================

    def complete_job(
        self,
        db: Session,
        job_id: int
    ):

        job = (

            db.query(
                publish_job_repository
                .model
            )

            .filter_by(id=job_id)

            .first()
        )

        if not job:

            return None

        job.completed_at = (
            datetime.utcnow()
        )

        db.commit()

        db.refresh(job)

        return job


publishing_service = (
    PublishingService()
)