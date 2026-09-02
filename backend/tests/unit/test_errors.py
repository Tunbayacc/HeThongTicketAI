from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers


def _build_app():
    from fastapi import FastAPI

    from app.core.logging import configure_logging
    from app.core.middleware import RequestContextMiddleware

    configure_logging("WARNING")
    app = FastAPI()

    @app.get("/app-error")
    async def app_error():
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Phiên đã hết hạn.")

    @app.get("/http-error")
    async def http_error():
        raise StarletteHTTPException(status_code=403, detail="Không có quyền")

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    # Mirror the real app topology: RequestContextMiddleware outermost so a
    # handled error's response flows back through its send_wrapper and picks up
    # the X-Request-ID header (same ordering as app/main.py create_app()).
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    return app


def test_app_error_body_and_status():
    resp = TestClient(_build_app()).get("/app-error")
    assert resp.status_code == 401
    body = resp.json()
    assert body == {"error_code": "AUTH_TOKEN_EXPIRED", "message": "Phiên đã hết hạn.", "details": None}


def test_handled_error_response_carries_request_id():
    resp = TestClient(_build_app()).get("/app-error")
    assert len(resp.headers["X-Request-ID"]) == 32


def test_http_exception_maps_to_error_body():
    resp = TestClient(_build_app()).get("/http-error")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "ACCESS_DENIED"


def test_unknown_500_is_json_error_body():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert "Traceback" not in resp.text and "RuntimeError" not in resp.text
