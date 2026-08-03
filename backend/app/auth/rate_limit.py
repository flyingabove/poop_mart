"""
In-memory rate limiting for auth endpoints.

Nothing protected /api/auth/login or /api/auth/signup from brute-force or
mass-account-creation abuse -- a real gap on a live, public app with real
user passwords.

Deliberately in-process/in-memory, not Redis-backed: this service runs as
a single Railway instance today (one `beta-backend` service, no horizontal
scaling configured -- see CLAUDE.md), so a process-local store is a real,
working limiter for the actual deployed architecture, not a stub pretending
to be one. If this service is ever scaled to multiple instances, a
per-instance limiter would silently under-enforce across instances --
that migration to a shared store (Redis) is a real follow-up, not
something to pretend is handled here.
"""
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> bool:
        """Record an attempt for `key`. Returns False if `key` has already
        hit max_attempts within the trailing window (attempt is still
        recorded either way, so a sustained attacker doesn't get free
        retries by exceeding the limit)."""
        now = time.time()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        allowed = len(hits) < self.max_attempts
        hits.append(now)
        return allowed

    def reset(self, key: str) -> None:
        """Clear attempts for `key` -- called on successful login so a
        legitimate user isn't penalized by their own earlier typos."""
        self._hits.pop(key, None)
