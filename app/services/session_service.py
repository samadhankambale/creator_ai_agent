import json
import redis
from app.core.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

# TTL: session data expires after 2 hours of inactivity
TTL = 7200


class SessionService:
    """
    All state stored in Redis so it survives server restarts
    and works correctly across multiple workers.
    """

    # ── Pending post ──────────────────────────────────

    def save_pending_post(self, phone: str, data: dict):
        redis_client.setex(f"session:pending:{phone}", TTL, json.dumps(data))

    def get_pending_post(self, phone: str) -> dict | None:
        val = redis_client.get(f"session:pending:{phone}")
        return json.loads(val) if val else None

    def delete_pending_post(self, phone: str):
        redis_client.delete(f"session:pending:{phone}")

    # ── Selected platforms ────────────────────────────

    def save_selected_platforms(self, phone: str, platforms: list):
        redis_client.setex(f"session:platforms:{phone}", TTL, json.dumps(platforms))

    def get_selected_platforms(self, phone: str) -> list:
        val = redis_client.get(f"session:platforms:{phone}")
        return json.loads(val) if val else []

    def delete_selected_platforms(self, phone: str):
        redis_client.delete(f"session:platforms:{phone}")

    # ── Schedule state ────────────────────────────────

    def set_waiting_for_schedule(self, phone: str, value: bool):
        if value:
            redis_client.setex(f"session:schedule_wait:{phone}", TTL, "1")
        else:
            redis_client.delete(f"session:schedule_wait:{phone}")

    def is_waiting_for_schedule(self, phone: str) -> bool:
        return redis_client.exists(f"session:schedule_wait:{phone}") == 1

    # ── Clear all session data for a user ─────────────

    def clear_all(self, phone: str):
        redis_client.delete(
            f"session:pending:{phone}",
            f"session:platforms:{phone}",
            f"session:schedule_wait:{phone}",
        )


session_service = SessionService()