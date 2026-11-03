"""Redis-backed login throttling shared by every API instance."""

from hashlib import sha256

from app.redis_state import get_redis_client, require_redis
from app.security import auth_settings


class LoginAttemptLimiter:
    _RECORD_FAILURE = """
    if redis.call('EXISTS', KEYS[2]) == 1 then
        return redis.call('TTL', KEYS[2])
    end
    local attempts = redis.call('INCR', KEYS[1])
    if attempts == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    if attempts >= tonumber(ARGV[2]) then
        redis.call('DEL', KEYS[1])
        redis.call('SET', KEYS[2], '1', 'EX', ARGV[3])
        return tonumber(ARGV[3])
    end
    return 0
    """

    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int, client=None, *, prefix: str | None = None):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._client = client
        self._prefix = prefix or auth_settings.redis_key_prefix

    @property
    def client(self):
        return self._client or get_redis_client()

    def _identifier(self, key: str) -> str:
        return sha256(key.encode("utf-8")).hexdigest()

    def _attempt_key(self, key: str) -> str:
        return f"{self._prefix}:login:attempts:{self._identifier(key)}"

    def _lock_key(self, key: str) -> str:
        return f"{self._prefix}:login:lock:{self._identifier(key)}"

    def blocked(self, *keys: str) -> int | None:
        def operation() -> int | None:
            seconds = 0
            for key in keys:
                seconds = max(seconds, max(0, self.client.ttl(self._lock_key(key))))
            return seconds or None
        return require_redis(operation)

    def record_failure(self, *keys: str) -> int | None:
        def operation() -> int | None:
            retry_after = 0
            for key in keys:
                lock_seconds = self.client.eval(
                    self._RECORD_FAILURE,
                    2,
                    self._attempt_key(key),
                    self._lock_key(key),
                    self.window_seconds,
                    self.max_attempts,
                    self.lockout_seconds,
                )
                retry_after = max(retry_after, int(lock_seconds))
            return retry_after or None
        return require_redis(operation)

    def record_success(self, *keys: str) -> None:
        require_redis(lambda: self.client.delete(*[
            item for key in keys for item in (self._attempt_key(key), self._lock_key(key))
        ]))