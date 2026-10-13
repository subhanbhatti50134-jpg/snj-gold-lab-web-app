"""In-memory failed-login limiter (per process, no extra dependency).

Disabled entirely when the limit is 0, which is how the test suite
configures it (see tests/conftest.py).
"""

import time
from collections import deque

from app.core.config import LOGIN_RATE_LIMIT

WINDOW_SECONDS = 60

_failures: dict[str, deque[float]] = {}


def _prune(key: str, now: float) -> deque[float]:
    hits = _failures.setdefault(key, deque())
    while hits and hits[0] <= now - WINDOW_SECONDS:
        hits.popleft()
    return hits


def is_blocked(key: str) -> bool:
    if LOGIN_RATE_LIMIT <= 0:
        return False

    return len(_prune(key, time.monotonic())) >= LOGIN_RATE_LIMIT


def record_failure(key: str) -> None:
    if LOGIN_RATE_LIMIT <= 0:
        return

    _prune(key, time.monotonic()).append(time.monotonic())


def clear_failures(key: str) -> None:
    _failures.pop(key, None)
