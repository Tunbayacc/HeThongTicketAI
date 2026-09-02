import logging

from starlette.testclient import TestClient


def build_app():
    from fastapi import FastAPI

    from app.core.logging import configure_logging
    from app.core.middleware import RequestContextMiddleware

    configure_logging("WARNING")
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"message": "pong"}

    app.add_middleware(RequestContextMiddleware)
    return app


def test_request_id_header_present():
    client = TestClient(build_app())
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert len(resp.headers["X-Request-ID"]) == 32


def test_access_log_contains_request_id(caplog):
    client = TestClient(build_app())
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/ping")
    assert any(r.request_id != "-" and r.path == "/ping" for r in caplog.records)
