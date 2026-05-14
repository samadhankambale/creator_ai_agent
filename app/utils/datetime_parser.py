import dateparser


def parse_schedule_datetime(
    text: str,
    timezone: str = "Asia/Kolkata"
):

    parsed_date = dateparser.parse(

        text,

        settings={

            "TIMEZONE":
            timezone,

            "RETURN_AS_TIMEZONE_AWARE":
            False,

            "PREFER_DATES_FROM":
            "future"
        }
    )

    return parsed_date


def is_schedule_request(
    text: str,
    timezone: str = "Asia/Kolkata"
):

    parsed_date = (
        parse_schedule_datetime(
            text,
            timezone
        )
    )

    return parsed_date is not None