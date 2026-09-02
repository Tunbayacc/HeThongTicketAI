import logging

from starlette.testclient import TestClient

from app.core.middleware import RequestContextMiddleware


def _build_app():
    from fastapi import FastAPI

    from app.core.logging import configure_logging, get_request_id

    configure_logging("WARNING")
    app = FastAPI()
    business = logging.getLogger("app.business")

    @app.get("/trace")
    async def trace():
        business.info("inside route")  # no request_id extra: relies on the contextvar
        return {"request_id": get_request_id()}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    app.add_middleware(RequestContextMiddleware)
    return app


def test_route_handler_sees_the_request_id_contextvar():
    client = TestClient(_build_app())
    resp = client.get("/trace")
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == resp.json()["request_id"]


def test_route_log_record_emitted(caplog):
    client = TestClient(_build_app())
    with caplog.at_level(logging.INFO, logger="app.business"):
        client.get("/trace")
    assert any(r.name == "app.business" and r.getMessage() == "inside route" for r in caplog.records)


def test_unhandled_error_still_logs_500_access_line(caplog):
    client = TestClient(_build_app(), raise_server_exceptions=False)
    with caplog.at_level(logging.INFO, logger="app.access"):
        resp = client.get("/boom")
    assert resp.status_code == 500
    recs = [r for r in caplog.records if r.name == "app.access"]
    assert any(getattr(r, "status_code", None) == 500 for r in recs)
    assert any(getattr(r, "request_id", "-") != "-" for r in recs)
