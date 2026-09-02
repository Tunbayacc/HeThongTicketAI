from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.public import router as public_router
from app.api.tickets import router as tickets_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import init_rate_limit

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # RequestContextMiddleware added last => runs first (outermost).
    application.add_middleware(RequestContextMiddleware)

    # Serve health at both prefixes: /health (direct probes) and /api/health
    # (same path survives the frontend nginx proxy_pass /api -> backend:8000).
    application.include_router(health_router, prefix="/health")
    application.include_router(health_router, prefix="/api/health")

    application.include_router(auth_router, prefix="/api/auth")

    application.include_router(public_router, prefix="/api/public")
    application.include_router(tickets_router, prefix="/api")

    # slowapi limiter bound to Settings.rate_limit_enabled (S2 public endpoints).
    init_rate_limit(application)

    # Standard JSON error body {error_code, message, details} on every HTTP error.
    register_exception_handlers(application)
    return application


app = create_app()
