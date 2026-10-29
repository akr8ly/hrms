"""Short-lived in-process login throttling.

Replace this store with Redis before running more than one API instance.
"""
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock


@dataclass
class _Attempts:
    timestamps: deque[datetime] = field(default_factory=deque)
    locked_until: datetime | None = None


class LoginAttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.lockout = timedelta(seconds=lockout_seconds)
        self._entries: dict[str, _Attempts] = defaultdict(_Attempts)
        self._lock = Lock()

    def _prune(self, entry: _Attempts, now: datetime) -> None:
        cutoff = now - self.window
        while entry.timestamps and entry.timestamps[0] <= cutoff:
            entry.timestamps.popleft()
        if entry.locked_until and entry.locked_until <= now:
            entry.locked_until = None

    def blocked(self, *keys: str) -> int | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            seconds = 0
            for key in keys:
                entry = self._entries[key]
                self._prune(entry, now)
                if entry.locked_until:
                    seconds = max(seconds, int((entry.locked_until - now).total_seconds()) + 1)
            return seconds or None

    def record_failure(self, *keys: str) -> int | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            retry_after = None
            for key in keys:
                entry = self._entries[key]
                self._prune(entry, now)
                entry.timestamps.append(now)
                if len(entry.timestamps) >= self.max_attempts:
                    entry.locked_until = now + self.lockout
                    entry.timestamps.clear()
                    retry_after = int(self.lockout.total_seconds())
            return retry_after

    def record_success(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._entries.pop(key, None)
