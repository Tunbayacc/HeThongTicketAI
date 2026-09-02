from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.ai.providers import ProviderError, build_provider
from app.core.config import get_settings
from app.db.session import engine

# No prefix here: main.py mounts this router at BOTH /health (direct probes)
# and /api/health (so the nginx proxy /api -> backend keeps the same path).
router = APIRouter(tags=["health"])

_EXPECTED_SCHEMA = {
    "users", "support_teams", "team_members", "tickets", "comments",
    "attachments", "ai_results", "ticket_history", "sla_policies",
    "refresh_tokens", "audit_logs",
}


@router.get("/live")
async def liveness() -> dict:
    # Pure process liveness: never depends on DB or AI (SRS 14.2).
    return {"status": "ok"}


@router.get("/ready")
async def readiness(response: Response) -> dict:
    # DB reachable AND migrations applied (alembic_version present + schema current).
    try:
        async with engine.connect() as conn:
            version_table = await conn.execute(
                text("SELECT to_regclass('public.alembic_version')")
            )
            if version_table.scalar() is None:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                return {"status": "error", "error_code": "DB_MIGRATION_MISSING",
                        "message": "alembic_version table not found"}
            table_rows = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE'"
                )
            )
            existing = {row[0] for row in table_rows}
            missing = _EXPECTED_SCHEMA - existing
            if missing:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                return {"status": "error", "error_code": "DB_SCHEMA_INCOMPLETE",
                        "message": f"missing tables: {sorted(missing)}"}
    except Exception as exc:  # noqa: BLE001 - degrade to 503 with a clean error body
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "error_code": "DB_UNAVAILABLE",
                "message": f"database unreachable: {type(exc).__name__}"}
    return {"status": "ok", "database": "ok"}


@router.get("/ai")
async def ai_status(response: Response) -> dict:
    # Reported separately per SRS 14.2; AI outage must not fail liveness.
    settings = get_settings()
    if settings.ai_provider == "gemini" and not settings.gemini_api_key:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "provider": settings.ai_provider,
                "reason": "missing_gemini_api_key"}
    if settings.ai_provider == "gemini":
        # Real probe (S4): cheap, token-free model lookup. AI outage must not fail
        # liveness/readiness, so degrade to a 503 with a clean error body.
        try:
            reachable = await build_provider().probe()
        except ProviderError as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unavailable", "provider": settings.ai_provider,
                    "reason": exc.code}
        if not reachable:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unavailable", "provider": settings.ai_provider,
                    "reason": "unreachable"}
        return {"status": "ok", "provider": settings.ai_provider, "probe": "ok"}
    return {"status": "ok", "provider": settings.ai_provider}
