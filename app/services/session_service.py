import json
import redis

from app.core.config import settings


redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)


class SessionService:

    # ==================================================
    # PENDING POST
    # ==================================================

    def save_pending_post(
        self,
        phone_number,
        post_data
    ):

        redis_client.set(

            f"pending_post:{phone_number}",

            json.dumps(post_data),

            ex=3600
        )

    def get_pending_post(
        self,
        phone_number
    ):

        data = redis_client.get(
            f"pending_post:{phone_number}"
        )

        if not data:
            return None

        return json.loads(data)

    def delete_pending_post(
        self,
        phone_number
    ):

        redis_client.delete(
            f"pending_post:{phone_number}"
        )

    # ==================================================
    # SCHEDULE MODE
    # ==================================================

    def enable_schedule_mode(
        self,
        phone_number
    ):

        redis_client.set(

            f"schedule_mode:{phone_number}",

            "true",

            ex=3600
        )

    def disable_schedule_mode(
        self,
        phone_number
    ):

        redis_client.delete(
            f"schedule_mode:{phone_number}"
        )

    def is_schedule_mode(
        self,
        phone_number
    ):

        data = redis_client.get(
            f"schedule_mode:{phone_number}"
        )

        return data == "true"

    # ==================================================
    # PLATFORM SELECTION
    # ==================================================

    def save_selected_platforms(
        self,
        phone_number,
        platforms
    ):

        redis_client.set(

            f"platforms:{phone_number}",

            json.dumps(platforms),

            ex=3600
        )

    def get_selected_platforms(
        self,
        phone_number
    ):

        data = redis_client.get(
            f"platforms:{phone_number}"
        )

        if not data:
            return []

        return json.loads(data)

    def delete_selected_platforms(
        self,
        phone_number
    ):

        redis_client.delete(
            f"platforms:{phone_number}"
        )


session_service = SessionService()