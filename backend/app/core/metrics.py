"""In-process request metrics for self-hosted monitoring.

Counts are in-memory (reset on restart) and exposed to admins via
GET /api/metrics — enough to spot error spikes without external
infrastructure. The last 50 five-hundred responses are kept for
triage.
"""

import threading
import time
from collections import deque

_STARTED_AT = time.time()
_lock = threading.Lock()
_total_requests = 0
_by_status_class: dict[str, int] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
_by_method: dict[str, int] = {}
_total_duration_ms = 0.0
_recent_errors: deque[dict] = deque(maxlen=50)


def record_request(
    method: str, path: str, status: int, duration_ms: float
) -> None:
    global _total_requests, _total_duration_ms
    with _lock:
        _total_requests += 1
        _total_duration_ms += duration_ms
        _by_method[method] = _by_method.get(method, 0) + 1
        bucket = f"{status // 100}xx"
        if bucket in _by_status_class:
            _by_status_class[bucket] += 1
        if status >= 500:
            _recent_errors.append(
                {
                    "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "method": method,
                    "path": path,
                    "status": status,
                    "duration_ms": round(duration_ms, 1),
                }
            )


def snapshot() -> dict:
    with _lock:
        total = _total_requests
        return {
            "uptime_seconds": round(time.time() - _STARTED_AT, 1),
            "total_requests": total,
            "by_status_class": dict(_by_status_class),
            "by_method": dict(_by_method),
            "avg_duration_ms": (
                round(_total_duration_ms / total, 1) if total else 0.0
            ),
            "recent_5xx": list(_recent_errors),
        }
