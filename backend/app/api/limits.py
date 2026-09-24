import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request

from app.core.config import settings

WINDOW_SECONDS = 600
_MAX_TRACKED_KEYS = 10_000

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def _client_ip(request: Request) -> str:
    # Behind a proxy (Render etc.) uvicorn runs with --proxy-headers, so this is
    # the real visitor address rather than the proxy's.
    return request.client.host if request.client else "unknown"


def _make_limiter(bucket: str, get_limit: Callable[[], int]):
    def dependency(request: Request) -> None:
        limit = get_limit()
        if limit <= 0:
            return

        now = time.monotonic()
        key = (bucket, _client_ip(request))
        window = _hits[key]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()

        if len(window) >= limit:
            retry_after = max(1, int(WINDOW_SECONDS - (now - window[0])))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Slow down — this demo allows {limit} of these every 10 minutes per visitor. "
                    f"Try again in about {max(1, retry_after // 60)} min."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)

        if len(_hits) > _MAX_TRACKED_KEYS:
            for stale in [k for k, v in _hits.items() if not v or now - v[-1] > WINDOW_SECONDS]:
                del _hits[stale]

    return dependency


limit_costly = _make_limiter("costly", lambda: settings.RATE_LIMIT_COSTLY_PER_10MIN)
limit_light = _make_limiter("light", lambda: settings.RATE_LIMIT_LIGHT_PER_10MIN)
