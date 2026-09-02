import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

access_logger = logging.getLogger("app.access")


class RequestContextMiddleware:
    """Assign a request_id (contextvar + response header) and log an access line.

    Pure ASGI, not BaseHTTPMiddleware: the downstream app runs in this same task,
    so the request_id contextvar set here IS visible inside route handlers and
    loggers (S0 ledger obligation S1-OBL-2). A raised exception that escapes the
    app (nothing has been sent) still produces a 500 access line so the failure is
    traceable (S1-OBL-1); FastAPI's global handler formats the body (Task 3).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                request_id = value.decode("latin-1")
                break

        token = request_id_var.set(request_id)
        start = time.perf_counter()
        state = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                headers = [(k, v) for k, v in message.get("headers", []) if k != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            access_logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": scope.get("method"),
                "path": scope.get("path"),
                "status_code": state["status"],
                "duration_ms": duration_ms,
            },
        )
