from pydantic import BaseModel, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers


def _build_app():
    from fastapi import FastAPI

    from app.core.logging import configure_logging
    from app.core.middleware import RequestContextMiddleware

    configure_logging("WARNING")
    app = FastAPI()

    class SampleBody(BaseModel):
        mode: str

        @field_validator("mode")
        @classmethod
        def _reject_boom(cls, value: str) -> str:
            if value == "boom":
                raise ValueError("boom-ctx")
            return value

    @app.get("/app-error")
    async def app_error():
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Phiên đã hết hạn.")

    @app.get("/http-error")
    async def http_error():
        raise StarletteHTTPException(status_code=403, detail="Không có quyền")

    @app.get("/bare-401")
    async def bare_401():
        raise StarletteHTTPException(status_code=401, detail="bad")

    @app.post("/validate")
    async def validate(body: SampleBody):
        return {"ok": body.mode}

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


def test_validation_error_is_error_envelope_and_serializable():
    client = TestClient(_build_app())
    resp = client.post("/validate", json={})
    assert resp.status_code == 422
    body = resp.json()  # parsing proves the response body is JSON-serializable
    assert body["error_code"] == "VALIDATION_ERROR"
    assert set(body) == {"error_code", "message", "details"}


def test_validation_error_with_validator_exception_stays_422():
    # Regression guard: a pydantic v2 validator raising ValueError embeds a live
    # exception in the error's `ctx`; without jsonable_encoder the details dict
    # cannot be json-serialized and this route would turn into a spurious 500.
    client = TestClient(_build_app())
    resp = client.post("/validate", json={"mode": "boom"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)


def test_bare_401_falls_back_to_auth_token_expired():
    # S1 binding: a bare framework 401 maps to AUTH_TOKEN_EXPIRED (no
    # UNAUTHENTICATED code exists), via the _FALLBACK transport envelope.
    resp = TestClient(_build_app()).get("/bare-401")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "AUTH_TOKEN_EXPIRED"
