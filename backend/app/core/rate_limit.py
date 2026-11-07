"""Small in-memory limiter for repeated failed login attempts.

Limitation: counters live in this process's memory. They reset on restart and are not shared
between multiple server processes. Move the counters to Redis when the app runs on more than
one worker (Redis is already planned for background jobs).

Memory is bounded by ``_MAX_TRACKED_KEYS`` and the bound is enforced so that flooding the limiter
with distinct keys cannot cheaply erase protection for a real target:

* Blocked keys (at ``max_attempts``) are never evicted to make room.
* Unblocked keys are evicted fewest-failures-first, then oldest-activity-first, in batches. To push
  out a key holding ``k`` failures an attacker must first fill the whole table with keys that hold
  at least ``k`` failures each, so the cost of resetting a counter grows with the counter.
* If every tracked key is blocked, new keys share one bounded overflow budget
  (``max_attempts * _OVERFLOW_MULTIPLIER`` failures per window across ALL untracked keys). Normal
  users keep working until that shared budget is spent; an attacker gets a fixed total number of
  guesses per window instead of unlimited ones. When the budget is spent, untracked keys are blocked
  until it recovers.
"""

import heapq
import math
import threading
import time
from collections import deque
from collections.abc import Callable

_MAX_TRACKED_KEYS = 10_000
_SWEEP_INTERVAL_SECONDS = 1.0
_EVICTION_BATCH_FRACTION = 10  # evict 1/10th of capacity at a time so eviction cost is amortised
_OVERFLOW_MULTIPLIER = 10


class FailedAttemptLimiter:
    """Blocks a key after `max_attempts` failures inside a sliding `window_seconds` window."""

    def __init__(self, max_attempts: int, window_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = float("-inf")
        # While now < _saturated_until, the table is full of blocked keys and new keys share the overflow budget.
        self._saturated_until = 0.0
        self._overflow_max = max(1, max_attempts * _OVERFLOW_MULTIPLIER)
        self._overflow: deque[float] = deque(maxlen=self._overflow_max)

    def _prune(self, key: str, now: float) -> deque[float] | None:
        attempts = self._failures.get(key)
        if attempts is None:
            return None
        while attempts and now - attempts[0] >= self._window_seconds:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
            return None
        return attempts

    def _prune_overflow(self, now: float) -> None:
        while self._overflow and now - self._overflow[0] >= self._window_seconds:
            self._overflow.popleft()

    def _sweep_expired(self, now: float) -> None:
        """Drop expired entries, at most once per interval so a flood cannot force a scan per call."""
        if now - self._last_sweep < _SWEEP_INTERVAL_SECONDS:
            return
        self._last_sweep = now
        for tracked_key in list(self._failures):
            self._prune(tracked_key, now)

    def _is_blocked(self, attempts: deque[float]) -> bool:
        return len(attempts) >= self._max_attempts

    def _overflow_retry_after(self, now: float) -> int:
        self._prune_overflow(now)
        if len(self._overflow) < self._overflow_max:
            return 0
        return max(1, math.ceil(self._overflow[0] + self._window_seconds - now))

    def retry_after(self, key: str) -> int:
        """Return seconds until another attempt is allowed, or 0 if the key is not blocked."""
        with self._lock:
            now = self._clock()
            attempts = self._prune(key, now)
            if attempts is None:
                if now < self._saturated_until:
                    return self._overflow_retry_after(now)
                return 0
            if not self._is_blocked(attempts):
                return 0
            return max(1, math.ceil(attempts[0] + self._window_seconds - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            attempts = self._prune(key, now)
            if attempts is None:
                if now < self._saturated_until:
                    self._prune_overflow(now)
                    self._overflow.append(now)
                    return
                if len(self._failures) >= _MAX_TRACKED_KEYS:
                    self._sweep_expired(now)
                if len(self._failures) >= _MAX_TRACKED_KEYS and not self._make_room():
                    self._prune_overflow(now)
                    self._overflow.append(now)
                    return
                attempts = self._failures.setdefault(key, deque())
            attempts.append(now)

    def _make_room(self) -> bool:
        """Evict a batch of unblocked keys (fewest failures, then least recent). False if none can go."""
        candidates = [
            (len(attempts), attempts[-1], tracked_key)
            for tracked_key, attempts in self._failures.items()
            if not self._is_blocked(attempts)
        ]
        if not candidates:
            self._saturated_until = min(
                attempts[0] + self._window_seconds for attempts in self._failures.values()
            )
            return False
        batch = max(1, _MAX_TRACKED_KEYS // _EVICTION_BATCH_FRACTION)
        for _, _, tracked_key in heapq.nsmallest(batch, candidates):
            del self._failures[tracked_key]
        return True

    def reset(self, key: str | None = None) -> None:
        """Forget one key (after a successful login) or everything (used by tests)."""
        with self._lock:
            if key is None:
                self._failures.clear()
                self._overflow.clear()
            else:
                self._failures.pop(key, None)
            self._saturated_until = 0.0


class RedisFailedAttemptLimiter:
    """Redis-backed fixed-window limiter shared by all API workers.

    Redis errors intentionally propagate: a configured distributed limiter must not silently
    degrade to per-process protection in production.
    """

    def __init__(self, redis_url: str, max_attempts: int, window_seconds: int, prefix: str = "bizpilot:limit") -> None:
        from redis import Redis
        self.client = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.prefix = prefix

    def _key(self, key: str) -> str:
        import hashlib
        digest = hashlib.sha256(key.encode()).hexdigest()
        return f"{self.prefix}:{digest}"

    def retry_after(self, key: str) -> int:
        redis_key = self._key(key)
        count = int(self.client.get(redis_key) or 0)
        if count < self.max_attempts:
            return 0
        return max(1, int(self.client.ttl(redis_key)))

    def record_failure(self, key: str) -> None:
        redis_key = self._key(key)
        self.client.eval(
            "local n = redis.call('INCR', KEYS[1]); if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; return n",
            1, redis_key, self.window_seconds,
        )

    def reset(self, key: str | None = None) -> None:
        if key is None:
            # Clear only this limiter's namespace (used by isolated test fixtures), never the whole DB.
            cursor = 0
            pattern = f"{self.prefix}:*"
            while True:
                cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=500)
                if keys:
                    self.client.delete(*keys)
                if cursor == 0:
                    break
            return
        self.client.delete(self._key(key))


def build_limiter(max_attempts: int, window_seconds: int, *, redis_url: str = "", prefix: str = "bizpilot:limit"):
    """Choose shared Redis protection when configured, otherwise retain bounded local dev/test behavior."""
    if redis_url:
        return RedisFailedAttemptLimiter(redis_url, max_attempts, window_seconds, prefix)
    return FailedAttemptLimiter(max_attempts, window_seconds)
