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


def test_500_traceback_log_carries_the_request_request_id(caplog):
    # NFR-OBS: the full traceback logged server-side for an unhandled 500 must be
    # correlatable to the request that caused it, i.e. carry the same request_id
    # as the 500 app.access line. The generic-Exception handler runs in
    # ServerErrorMiddleware, AFTER RequestContextMiddleware has reset the
    # contextvar, so it must read the id off the ASGI scope, not the contextvar.
    from app.core.errors import register_exception_handlers

    app = _build_app()
    register_exception_handlers(app)
    client = TestClient(app, raise_server_exceptions=False)
    # Single root at_level(INFO): caplog's one LogCaptureHandler filters on a
    # single shared level, so a nested at_level would drop the INFO access record
    # while the ERROR traceback record is captured (and vice versa).
    with caplog.at_level(logging.INFO):
        resp = client.get("/boom")
    assert resp.status_code == 500
    err_recs = [
        r for r in caplog.records if r.name == "app.error" and r.getMessage() == "unhandled error"
    ]
    assert err_recs, "expected the 'unhandled error' traceback log"
    err_req_id = getattr(err_recs[0], "request_id", "-")
    assert err_req_id != "-", "traceback log request_id should be the request's, not '-'"
    assert any(
        getattr(r, "status_code", None) == 500 and getattr(r, "request_id", "-") == err_req_id
        for r in caplog.records
        if r.name == "app.access"
    )
