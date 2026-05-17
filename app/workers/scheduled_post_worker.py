import traceback

from app.workers.celery_worker import (
    celery_app
)

from app.database.session import (
    SessionLocal
)

from app.repositories.publish_job_repository import (
    publish_job_repository
)

from app.repositories.post_repository import (
    post_repository
)

from app.services.social_account_service import (
    social_account_service
)

from app.services.publishing_service import (
    publishing_service
)

from app.integrations.whatsapp.whatsapp_client import (
    send_message_sync
)


@celery_app.task(
    name="app.workers.scheduled_post_worker.process_publish_job"
)
def process_publish_job(
    job_id
):

    print("================================")
    print("PROCESSING JOB")
    print("================================")

    print("JOB ID:")
    print(job_id)

    db = SessionLocal()

    try:

        # ============================================
        # GET JOB
        # ============================================

        job = (
            publish_job_repository
            .get_job_by_id(
                db,
                job_id
            )
        )

        print("JOB:")
        print(job)

        if not job:

            print("JOB NOT FOUND")

            return

        # ============================================
        # GET POST
        # ============================================

        post = (
            post_repository
            .get_post_by_id(
                db,
                job.post_id
            )
        )

        print("POST:")
        print(post)

        if not post:

            print("POST NOT FOUND")

            return

        # ============================================
        # GET ACCOUNT
        # ============================================

        account = (
            social_account_service
            .get_connected_account(

                db=db,

                whatsapp_number=
                post.user.whatsapp_number,

                platform=
                job.platform
            )
        )

        print("ACCOUNT:")
        print(account)

        if not account:

            print("ACCOUNT NOT FOUND")

            send_message_sync(

                post.user.whatsapp_number,

                (
                    f"❌ {job.platform.title()} "
                    f"account not connected"
                )
            )

            return

        print("PLATFORM:")
        print(job.platform)

        print("ACCOUNT USER ID:")
        print(account.platform_user_id)

        # ============================================
        # START PUBLISHING
        # ============================================

        result = (
            publishing_service
            .publish_post(

                platform=
                job.platform,

                caption=
                post.caption,

                image_url=
                post.image_url,

                account=
                account
            )
        )

        print("PUBLISH RESULT:")
        print(result)

        # ============================================
        # SUCCESS
        # ============================================

        if result.get("success"):

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="success"
            )

            # ----------------------------------------
            # SEND SUCCESS WHATSAPP MESSAGE
            # ----------------------------------------

            success_message = (

                f"✅ Successfully published on "
                f"{job.platform.title()}"
            )

            send_message_sync(

                post.user.whatsapp_number,

                success_message
            )

            print(
                "POST SUCCESSFULLY PUBLISHED"
            )

        # ============================================
        # FAILED
        # ============================================

        else:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                str(result)
            )

            error_message = (

                f"❌ Failed to publish on "
                f"{job.platform.title()}"
            )

            send_message_sync(

                post.user.whatsapp_number,

                error_message
            )

            print("PUBLISH FAILED")

    except Exception as e:

        print("WORKER ERROR:")
        print(str(e))

        traceback.print_exc()

        try:

            send_message_sync(

                post.user.whatsapp_number,

                (
                    "❌ Publishing failed due "
                    "to server error"
                )
            )

        except Exception:

            pass

    finally:

        db.close()