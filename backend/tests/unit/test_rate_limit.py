import json

import pytest
from limits import parse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit

from app.core.rate_limit import _rate_limit_exceeded_handler


def _exceeded() -> RateLimitExceeded:
    # Installed slowapi 0.1.10 requires a Limit arg (no no-arg constructor), so build
    # the same exception a real "20/hour" rate-limit hit would raise.
    return RateLimitExceeded(
        Limit(parse("20/hour"), get_remote_address, None, False, None, None, None, 1, False)
    )


async def test_rate_limit_handler_returns_uniform_429_body():
    resp = await _rate_limit_exceeded_handler(None, _exceeded())
    assert resp.status_code == 429
    body = json.loads(resp.body)
    assert body == {"error_code": "RATE_LIMITED", "message": body["message"], "details": None}
    assert body["error_code"] == "RATE_LIMITED"


def test_auth_login_rate_setting_and_route_configured():
    from app.api.auth import router as auth_router
    from app.core.config import get_settings

    settings = get_settings()
    assert hasattr(settings, "auth_login_rate")
    assert settings.auth_login_rate == "10/minute"

    auth_paths = [r.path for r in auth_router.routes]
    assert "/login" in auth_paths
