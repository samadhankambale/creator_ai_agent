import json
import redis
from app.core.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

TTL = 7200  # 2 hours


class SessionService:

    # ── State machine ─────────────────────────────────
    # Tracks exactly where user is in the flow.
    # Prevents old buttons/messages triggering wrong actions.

    def set_state(self, phone: str, state: str):
        redis_client.setex(f"s:state:{phone}", TTL, state)

    def get_state(self, phone: str) -> str:
        return redis_client.get(f"s:state:{phone}") or "idle"

    # ── Pending post ──────────────────────────────────

    def save_pending_post(self, phone: str, data: dict):
        redis_client.setex(f"s:post:{phone}", TTL, json.dumps(data))

    def get_pending_post(self, phone: str) -> dict | None:
        val = redis_client.get(f"s:post:{phone}")
        return json.loads(val) if val else None

    def delete_pending_post(self, phone: str):
        redis_client.delete(f"s:post:{phone}")

    # ── Selected platforms ────────────────────────────

    def save_selected_platforms(self, phone: str, platforms: list):
        redis_client.setex(f"s:platforms:{phone}", TTL, json.dumps(platforms))

    def get_selected_platforms(self, phone: str) -> list:
        val = redis_client.get(f"s:platforms:{phone}")
        return json.loads(val) if val else []

    def delete_selected_platforms(self, phone: str):
        redis_client.delete(f"s:platforms:{phone}")

    # ── Schedule state ────────────────────────────────

    def set_waiting_for_schedule(self, phone: str, value: bool):
        from app.api.whatsapp_webhook import STATE_WAITING_SCHED, STATE_IDLE
        self.set_state(phone, STATE_WAITING_SCHED if value else STATE_IDLE)

    def is_waiting_for_schedule(self, phone: str) -> bool:
        from app.api.whatsapp_webhook import STATE_WAITING_SCHED
        return self.get_state(phone) == STATE_WAITING_SCHED

    # ── Generated images ──────────────────────────────

    def save_generated_images(self, phone: str, images: list):
        redis_client.setex(f"s:gen_imgs:{phone}", TTL, json.dumps(images))

    def get_generated_images(self, phone: str) -> list:
        val = redis_client.get(f"s:gen_imgs:{phone}")
        return json.loads(val) if val else []

    def delete_generated_images(self, phone: str):
        redis_client.delete(f"s:gen_imgs:{phone}")

    # ── Pending caption ───────────────────────────────

    def save_pending_caption(self, phone: str, caption: str):
        redis_client.setex(f"s:caption:{phone}", TTL, caption)

    def get_pending_caption(self, phone: str) -> str | None:
        return redis_client.get(f"s:caption:{phone}")

    def delete_pending_caption(self, phone: str):
        redis_client.delete(f"s:caption:{phone}")

    # ── Pending prompt ────────────────────────────────

    def save_pending_prompt(self, phone: str, prompt: str):
        redis_client.setex(f"s:prompt:{phone}", TTL, prompt)

    def get_pending_prompt(self, phone: str) -> str | None:
        return redis_client.get(f"s:prompt:{phone}")

    def delete_pending_prompt(self, phone: str):
        redis_client.delete(f"s:prompt:{phone}")

    # ── Clear ALL session data ────────────────────────
    # Called at start of every new post AND after posting

    def clear_all(self, phone: str):
        redis_client.delete(
            f"s:state:{phone}",
            f"s:post:{phone}",
            f"s:platforms:{phone}",
            f"s:gen_imgs:{phone}",
            f"s:caption:{phone}",
            f"s:prompt:{phone}",
        )


session_service = SessionService()