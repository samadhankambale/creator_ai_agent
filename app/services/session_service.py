import json
import redis

from app.core.config import settings


redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)


class SessionService:
    
    def __init__(self):

        self.pending_posts = {}

        self.selected_platforms = {}

        self.waiting_for_schedule = {}

    # =================================================
    # PENDING POST
    # =================================================

    def save_pending_post(
        self,
        phone_number,
        post_data
    ):

        self.pending_posts[
            phone_number
        ] = post_data

    def get_pending_post(
        self,
        phone_number
    ):

        return self.pending_posts.get(
            phone_number
        )

    def delete_pending_post(
        self,
        phone_number
    ):

        if (
            phone_number
            in self.pending_posts
        ):

            del self.pending_posts[
                phone_number
            ]

    # =================================================
    # SELECTED PLATFORMS
    # =================================================

    def save_selected_platforms(
        self,
        phone_number,
        platforms
    ):

        self.selected_platforms[
            phone_number
        ] = platforms

    def get_selected_platforms(
        self,
        phone_number
    ):

        return self.selected_platforms.get(

            phone_number,

            []
        )

    def delete_selected_platforms(
        self,
        phone_number
    ):

        if (
            phone_number
            in self.selected_platforms
        ):

            del self.selected_platforms[
                phone_number
            ]

    # =================================================
    # SCHEDULE STATE
    # =================================================

    def set_waiting_for_schedule(
        self,
        phone_number,
        value
    ):

        self.waiting_for_schedule[
            phone_number
        ] = value

    def is_waiting_for_schedule(
        self,
        phone_number
    ):

        return self.waiting_for_schedule.get(

            phone_number,

            False
        )

    def clear_schedule_state(
        self,
        phone_number
    ):

        if (
            phone_number
            in self.waiting_for_schedule
        ):

            del self.waiting_for_schedule[
                phone_number
            ]


session_service = (
    SessionService()
)