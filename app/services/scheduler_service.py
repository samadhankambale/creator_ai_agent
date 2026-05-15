from app.workers.scheduled_post_worker import (
    process_scheduled_jobs
)


class SchedulerService:

    def run_scheduler(self):

        process_scheduled_jobs.delay()


scheduler_service = SchedulerService()