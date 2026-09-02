"""slowapi limiter for the /public endpoints (design spec 3; SRS 8.3 429).

Only /public/* is rate-limited in S2 (Controller decision 4). The limiter's
`enabled` flag is bound to Settings.rate_limit_enabled at app init, so the
integration suite runs with RATE_LIMIT_ENABLED=false. The 429 body keeps the
uniform {error_code, message, details} envelope (error_code RATE_LIMITED).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address)


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMITED",
            "message": "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn, vui lòng thử lại sau.",
            "details": None,
        },
    )


def init_rate_limit(app: FastAPI) -> None:
    settings = get_settings()
    limiter.enabled = settings.rate_limit_enabled
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
