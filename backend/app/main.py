from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

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

    return application


app = create_app()
