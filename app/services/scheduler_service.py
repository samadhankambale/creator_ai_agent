from datetime import datetime
import dateparser


class SchedulerService:

    def parse_schedule_time(self, text: str) -> datetime | None:
        """
        Parse natural language like 'tomorrow 9am', 'after 2 hours', 'tonight 8pm'.
        Returns a future datetime or None if parsing fails / time is in the past.
        """
        try:
            parsed = dateparser.parse(
                text.strip(),
                settings={
                    "TIMEZONE": "Asia/Kolkata",
                    "RETURN_AS_TIMEZONE_AWARE": False,
                    "PREFER_DATES_FROM": "future",
                },
            )

            if not parsed:
                return None

            if parsed <= datetime.now():
                print("SCHEDULE PARSE: time is in the past")
                return None

            print(f"SCHEDULE PARSED: {parsed}")
            return parsed

        except Exception as e:
            print(f"SCHEDULE PARSE ERROR: {e}")
            return None


scheduler_service = SchedulerService()