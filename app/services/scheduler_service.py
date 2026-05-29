from datetime import datetime, timezone, timedelta
import dateparser
import re

MAX_SCHEDULE_WEEKS = 4  # Cap at 4 weeks


class SchedulerService:

    def parse_schedule_time(self, text: str) -> dict:
        """
        Parse natural language schedule input.
        Returns dict: {"utc": datetime|None, "error": str|None}
        - utc: parsed UTC datetime if valid
        - error: user-friendly error message if invalid
        """
        original = text.strip()
        text = original.lower()

        # Fix common spelling mistakes
        text = self._fix_spelling(text)

        # Pre-process common phrases
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
            "after three weeks": "in 21 days",
            "after 3 weeks": "in 21 days",
            "after four weeks": "in 28 days",
            "after 4 weeks": "in 28 days",
            "one week": "in 7 days",
            "1 week": "in 7 days",
            # Cap months to 4 weeks
            "after one month": "in 28 days",
            "after 1 month": "in 28 days",
            "after two months": "in 28 days",
            "after 2 months": "in 28 days",
            "after three months": "in 28 days",
            "after 3 months": "in 28 days",
            "next month": "in 28 days",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Try dateparser
        result = self._try_dateparser(text)
        if not result:
            result = self._try_day_time_extraction(text)

        if not result:
            return {"utc": None, "error": "Could not understand the schedule. Try: 'tomorrow 9am', 'monday 5pm', 'after 2 hours'"}

        # Cap at 4 weeks
        max_dt = datetime.utcnow() + timedelta(weeks=MAX_SCHEDULE_WEEKS)
        if result > max_dt:
            capped = max_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            print(f"SCHEDULE: capped from {result} to {capped}")
            IST = timezone(timedelta(hours=5, minutes=30))
            cap_ist = capped.replace(tzinfo=timezone.utc).astimezone(IST)
            return {
                "utc": capped,
                "warning": f"Scheduling is limited to 4 weeks. Scheduled for {cap_ist.strftime('%d %b %Y at %I:%M %p IST')} instead."
            }

        return {"utc": result, "error": None}

    def _fix_spelling(self, text: str) -> str:
        """Fix common spelling mistakes in schedule inputs."""
        fixes = {
            "tommorow": "tomorrow",
            "tommorrow": "tomorrow",
            "tomorro": "tomorrow",
            "yasterday": "yesterday",
            "mnday": "monday",
            "tueday": "tuesday",
            "wenesday": "wednesday",
            "wednesady": "wednesday",
            "thrusday": "thursday",
            "thurday": "thursday",
            "fiday": "friday",
            "saterday": "saturday",
            "satorday": "saturday",
            "sunnday": "sunday",
            "sunady": "sunday",
            "minuts": "minutes",
            "minuets": "minutes",
            "houres": "hours",
            "mornig": "morning",
            "tonigt": "tonight",
            "aftr": "after",
            "afer": "after",
            "weeek": "week",
            "mnth": "month",
        }
        for wrong, correct in fixes.items():
            text = text.replace(wrong, correct)
        return text

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
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text, re.IGNORECASE)
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        found_day = next((d for d in days if d in text), None)

        if found_day:
            query = f"{found_day} {time_match.group(0)}" if time_match else found_day
            try:
                parsed = dateparser.parse(query, settings={
                    "TIMEZONE": "Asia/Kolkata",
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "PREFER_DATES_FROM": "future",
                })
                if parsed:
                    return self._to_utc(parsed)
            except Exception:
                pass
        return None

    def _to_utc(self, parsed) -> datetime | None:
        try:
            utc = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            if utc <= datetime.utcnow():
                return None
            IST = timezone(timedelta(hours=5, minutes=30))
            ist = parsed.astimezone(IST)
            print(f"SCHEDULE PARSED: {ist.strftime('%d %b %Y %I:%M %p IST')} → UTC: {utc}")
            return utc
        except Exception as e:
            print(f"SCHEDULE UTC CONVERT ERROR: {e}")
            return None

    def format_ist(self, utc_dt: datetime) -> str:
        IST = timezone(timedelta(hours=5, minutes=30))
        ist = utc_dt.replace(tzinfo=timezone.utc).astimezone(IST)
        return ist.strftime("%d %b %Y at %I:%M %p IST")


scheduler_service = SchedulerService()