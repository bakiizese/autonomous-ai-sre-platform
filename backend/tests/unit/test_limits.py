from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import limits


def _app_with_limit(get_limit):
    app = FastAPI()
    dep = limits._make_limiter("t", get_limit)

    @app.get("/x", dependencies=[Depends(dep)])
    def x():
        return {"ok": True}

    return TestClient(app)


def test_allows_up_to_the_limit_then_429():
    client = _app_with_limit(lambda: 3)

    assert [client.get("/x").status_code for _ in range(3)] == [200, 200, 200]
    blocked = client.get("/x")

    assert blocked.status_code == 429
    assert "3 of these every 10 minutes" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) > 0


def test_zero_disables_the_limit():
    client = _app_with_limit(lambda: 0)
    assert all(client.get("/x").status_code == 200 for _ in range(20))


def test_window_expires():
    client = _app_with_limit(lambda: 1)
    # Patch the limiter's own `time` reference, not time.monotonic globally —
    # the event loop under TestClient also reads that clock.
    with patch("app.api.limits.time") as fake_time:
        fake_time.monotonic.side_effect = [0.0, 1.0, limits.WINDOW_SECONDS + 5.0]
        assert client.get("/x").status_code == 200
        assert client.get("/x").status_code == 429
        assert client.get("/x").status_code == 200


def test_limits_are_per_bucket():
    app = FastAPI()
    a = limits._make_limiter("a", lambda: 1)
    b = limits._make_limiter("b", lambda: 1)

    @app.get("/a", dependencies=[Depends(a)])
    def route_a():
        return 1

    @app.get("/b", dependencies=[Depends(b)])
    def route_b():
        return 1

    client = TestClient(app)
    assert client.get("/a").status_code == 200
    assert client.get("/b").status_code == 200
    assert client.get("/a").status_code == 429


@pytest.mark.parametrize("name", ["limit_costly", "limit_light"])
def test_configured_limiters_exist(name):
    assert callable(getattr(limits, name))
