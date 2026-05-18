from datetime import (
    datetime
)

from dateutil import parser

from app.workers.scheduled_post_worker import (
    process_publish_job
)


class SchedulerService:

    # =================================================
    # NLP DATE/TIME PARSER
    # =================================================

    def parse_schedule_time(
        self,
        text
    ):

        try:

            print("================================")
            print("NLP SCHEDULE PARSER")
            print("================================")

            print("INPUT:")
            print(text)

            # =========================================
            # CLEAN INPUT
            # =========================================

            cleaned_text = (
                text
                .strip()
                .lower()
            )

            # =========================================
            # CURRENT TIME
            # =========================================

            now = datetime.now()

            # =========================================
            # NLP PARSING
            # =========================================

            parsed_datetime = parser.parse(

                cleaned_text,

                fuzzy=True,

                default=now
            )

            print("PARSED DATETIME:")
            print(parsed_datetime)

            # =========================================
            # INVALID PAST TIME
            # =========================================

            if parsed_datetime <= now:

                print(
                    "PAST TIME DETECTED"
                )

                return None

            # =========================================
            # SUCCESS
            # =========================================

            return parsed_datetime

        except Exception as e:

            print(
                "SCHEDULE PARSE ERROR:"
            )

            print(str(e))

            return None

    # =================================================
    # QUEUE JOB
    # =================================================

    def queue_publish_job(
        self,
        job_id
    ):

        try:

            print("================================")
            print("QUEUEING PUBLISH JOB")
            print("================================")

            print("JOB ID:")
            print(job_id)

            process_publish_job.delay(
                job_id
            )

            print(
                "JOB QUEUED SUCCESSFULLY"
            )

        except Exception as e:

            print(
                "QUEUE JOB ERROR:"
            )

            print(str(e))


scheduler_service = (
    SchedulerService()
)