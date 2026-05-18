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

from app.core.config import (
    settings
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

        print("POST FOUND")

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

        # ============================================
        # ACCOUNT NOT CONNECTED
        # ============================================

        if not account:

            print(
                "ACCOUNT NOT CONNECTED"
            )

            # ----------------------------------------
            # PLATFORM CONNECT ROUTES
            # ----------------------------------------

            platform_connect_routes = {

                "instagram":
                "/oauth/meta/connect",

                "facebook":
                "/oauth/meta/connect",

                "linkedin":
                "/oauth/linkedin/connect",

                "twitter":
                "/oauth/twitter/connect"
            }

            route = (
                platform_connect_routes.get(
                    job.platform
                )
            )

            # ----------------------------------------
            # GENERATE URL
            # ----------------------------------------

            if route:

                connect_url = (

                    f"{settings.APP_BASE_URL}"
                    f"{route}"
                    f"?whatsapp_number="
                    f"{post.user.whatsapp_number}"
                )

            else:

                connect_url = (
                    settings.APP_BASE_URL
                )

            print("CONNECT URL:")
            print(connect_url)

            # ----------------------------------------
            # SEND MESSAGE
            # ----------------------------------------

            message = (

                f"⚠️ Your "
                f"{job.platform.title()} "
                f"account is not connected.\n\n"

                f"Connect here:\n"
                f"{connect_url}"
            )

            send_message_sync(

                post.user.whatsapp_number,

                message
            )

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                "Account not connected"
            )

            return

        print("ACCOUNT CONNECTED")

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

            success_message = (

                f"✅ Successfully published "
                f"on {job.platform.title()}"
            )

            print(success_message)

            send_message_sync(

                post.user.whatsapp_number,

                success_message
            )

            print(
                "POST SUCCESSFULLY PUBLISHED"
            )

        # ============================================
        # FAILURE
        # ============================================

        else:

            publish_job_repository.update_job_status(

                db=db,

                job_id=job.id,

                status="failed",

                error_message=
                str(result)
            )

            failure_message = (

                f"❌ Failed to publish "
                f"on {job.platform.title()}"
            )

            print(failure_message)

            send_message_sync(

                post.user.whatsapp_number,

                failure_message
            )

            print(
                "PUBLISH FAILED"
            )

    # ================================================
    # EXCEPTION
    # # ================================================
    
    except Exception as e:

        print("================================")
        print("WORKER ERROR")
        print("================================")

        print(str(e))

        traceback.print_exc()

        error_message = str(e)

        # --------------------------------------------
        # SEND REAL ERROR
        # --------------------------------------------

        try:

            send_message_sync(

                post.user.whatsapp_number,

                (
                    "❌ Publishing failed\n\n"
                    f"Error:\n{error_message}"
                )
            )

        except Exception as inner_error:

            print(
                "WHATSAPP SEND ERROR:"
            )

            print(str(inner_error))
    

    # except Exception as e:

    #     print("WORKER ERROR:")
    #     print(str(e))

    #     traceback.print_exc()

    #     try:

    #         send_message_sync(

    #             post.user.whatsapp_number,

    #             (
    #                 "❌ Publishing failed "
    #                 "due to server error"
    #             )
    #         )

    #     except Exception:

    #         pass

    # ================================================
    # CLOSE DB
    # ================================================

    finally:

        db.close()