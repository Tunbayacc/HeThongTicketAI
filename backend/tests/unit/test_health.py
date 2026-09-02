from starlette.testclient import TestClient


def _client():
    from app.core.logging import configure_logging
    from app.main import app

    configure_logging("WARNING")
    return TestClient(app)


def test_liveness_ok():
    resp = _client().get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_ai_reports_provider():
    resp = _client().get("/health/ai")
    assert resp.status_code == 200
    body = resp.json()
    assert "provider" in body
    assert body["status"] in {"ok", "unavailable"}


def test_readiness_returns_503_json_when_db_down(monkeypatch):
    # Deterministic regardless of whether a local Postgres happens to be running:
    # point the health router at an obviously-dead endpoint (refused => fast error).
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.api import health

    monkeypatch.setattr(
        health,
        "engine",
        create_async_engine("postgresql+asyncpg://x:x@127.0.0.1:1/nope"),
    )
    resp = _client().get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error_code"] == "DB_UNAVAILABLE"
