"""Standard error body {error_code, message, details} and global handlers (SRS 5.2/8.3/10.2)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id

logger = logging.getLogger("app.error")

# Fallback codes when a plain HTTPException carries no error_code in its detail.
# SRS 10.2 has no code for a bare framework 401, so per the S1 decision every
# unusable-token case reads AUTH_TOKEN_EXPIRED (deps.py also raises this for
# missing/expired/invalid tokens). _FALLBACK is a transport envelope for statuses
# §10.2 (business-only) does not cover (404/405/422/500 etc.).
_FALLBACK = {
    400: "BAD_REQUEST",
    401: "AUTH_TOKEN_EXPIRED",
    403: "ACCESS_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


class AppError(Exception):
    """Business error that maps 1:1 to an HTTP response (error_code per SRS 10.2)."""

    def __init__(self, status_code: int, error_code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": exc.error_code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            error_code = exc.detail.get("error_code", _FALLBACK.get(exc.status_code, "ERROR"))
            message = exc.detail.get("message", exc.detail.get("detail", ""))
        else:
            error_code = _FALLBACK.get(exc.status_code, "ERROR")
            message = str(exc.detail) if exc.detail else error_code
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_code": error_code, "message": message, "details": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Dữ liệu không hợp lệ.",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback with request_id for NFR-OBS; never send it to the client.
        logger.error("unhandled error", exc_info=exc, extra={"request_id": get_request_id()})
        return JSONResponse(
            status_code=500,
            content={"error_code": "INTERNAL_ERROR", "message": "Đã xảy ra lỗi nội bộ.", "details": None},
        )
