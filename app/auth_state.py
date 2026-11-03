"""Redis-backed token session and revocation state."""

from datetime import datetime, timezone

from app.redis_state import get_redis_client, require_redis
from app.security import auth_settings


class TokenStateStore:
    def __init__(self, client=None, *, prefix: str | None = None) -> None:
        self._client = client
        self._prefix = prefix or auth_settings.redis_key_prefix

    @property
    def client(self):
        return self._client or get_redis_client()

    def _active_key(self, token_id: str) -> str:
        return f"{self._prefix}:auth:active:{token_id}"

    def _revoked_key(self, token_id: str) -> str:
        return f"{self._prefix}:auth:revoked:{token_id}"

    @staticmethod
    def _remaining_seconds(expires_at: int) -> int:
        return max(0, expires_at - int(datetime.now(timezone.utc).timestamp()))

    def activate(self, *, token_id: str, expires_at: int) -> None:
        lifetime = min(auth_settings.auth_session_idle_seconds, self._remaining_seconds(expires_at))
        if lifetime <= 0:
            return
        require_redis(lambda: self.client.set(self._active_key(token_id), "1", ex=lifetime))

    def validate_and_touch(self, *, token_id: str, expires_at: int) -> bool:
        remaining = self._remaining_seconds(expires_at)
        if remaining <= 0:
            return False
        lifetime = min(auth_settings.auth_session_idle_seconds, remaining)

        def operation() -> bool:
            if self.client.get(self._revoked_key(token_id)) is not None:
                return False
            active_key = self._active_key(token_id)
            if self.client.ttl(active_key) <= 0:
                return False
            self.client.expire(active_key, lifetime)
            return True

        return require_redis(operation)

    def revoke(self, *, token_id: str, expires_at: int) -> None:
        lifetime = self._remaining_seconds(expires_at)
        if lifetime <= 0:
            return

        def operation() -> None:
            pipeline = self.client.pipeline(transaction=True)
            pipeline.delete(self._active_key(token_id))
            pipeline.set(self._revoked_key(token_id), "1", ex=lifetime)
            pipeline.execute()

        require_redis(operation)


token_state = TokenStateStore()