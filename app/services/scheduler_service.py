from datetime import datetime, timezone, timedelta
import dateparser
import re


class SchedulerService:

    def parse_schedule_time(self, text: str) -> datetime | None:
        """
        Parse natural language schedule input.
        Tries dateparser first, falls back to Groq for complex expressions.
        Returns UTC datetime or None.
        """
        text = text.strip().lower()

        # Pre-process common phrases dateparser misses
        replacements = {
            "tonight": "today",
            "tonite": "today",
            "next monday": "monday",
            "next tuesday": "tuesday",
            "next wednesday": "wednesday",
            "next thursday": "thursday",
            "next friday": "friday",
            "next saturday": "saturday",
            "next sunday": "sunday",
            "aaj": "today",
            "kal": "tomorrow",
            "after one week": "in 7 days",
            "after 1 week": "in 7 days",
            "after two weeks": "in 14 days",
            "after 2 weeks": "in 14 days",
            "after one month": "in 30 days",
            "after 1 month": "in 30 days",
            "one week": "in 7 days",
            "1 week": "in 7 days",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Try dateparser first
        result = self._try_dateparser(text)
        if result:
            return result

        # For complex expressions like "next monday at 5pm" or "in 7 days on monday at 5pm"
        # Extract day name + time separately
        result = self._try_day_time_extraction(text)
        if result:
            return result

        return None

    def _try_dateparser(self, text: str) -> datetime | None:
        try:
            parsed = dateparser.parse(
                text,
                settings={
                    "TIMEZONE": "Asia/Kolkata",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "PREFER_DATES_FROM": "future",
                    "PREFER_DAY_OF_MONTH": "first",
                },
            )
            if not parsed:
                return None
            return self._to_utc(parsed)
        except Exception as e:
            print(f"DATEPARSER ERROR: {e}")
            return None

    def _try_day_time_extraction(self, text: str) -> datetime | None:
        """Handle patterns like 'in 7 days on monday at 5pm'"""
        # Extract time from text
        time_match = re.search(
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            text, re.IGNORECASE
        )
        # Extract day name
        days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        found_day = None
        for day in days:
            if day in text:
                found_day = day
                break

        if found_day and time_match:
            # Parse day + time
            time_str = time_match.group(0)
            try:
                parsed = dateparser.parse(
                    f"{found_day} {time_str}",
                    settings={
                        "TIMEZONE": "Asia/Kolkata",
                        "RETURN_AS_TIMEZONE_AWARE": True,
                        "PREFER_DATES_FROM": "future",
                    },
                )
                if parsed:
                    return self._to_utc(parsed)
            except Exception:
                pass
        elif found_day:
            try:
                parsed = dateparser.parse(
                    found_day,
                    settings={
                        "TIMEZONE": "Asia/Kolkata",
                        "RETURN_AS_TIMEZONE_AWARE": True,
                        "PREFER_DATES_FROM": "future",
                    },
                )
                if parsed:
                    return self._to_utc(parsed)
            except Exception:
                pass
        return None

    def _to_utc(self, parsed) -> datetime | None:
        try:
            utc = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            if utc <= datetime.utcnow():
                print(f"SCHEDULE: time is in the past: {utc}")
                return None
            IST = timezone(timedelta(hours=5, minutes=30))
            ist = parsed.astimezone(IST)
            print(f"SCHEDULE PARSED: {ist.strftime('%d %b %Y %I:%M %p IST')} → UTC: {utc}")
            return utc
        except Exception as e:
            print(f"SCHEDULE UTC CONVERT ERROR: {e}")
            return None

    def format_ist(self, utc_dt: datetime) -> str:
        """Format UTC datetime as IST string for display."""
        IST = timezone(timedelta(hours=5, minutes=30))
        ist = utc_dt.replace(tzinfo=timezone.utc).astimezone(IST)
        return ist.strftime("%d %b %Y at %I:%M %p IST")


scheduler_service = SchedulerService()