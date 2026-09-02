import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            # Prefer the explicit extra (set by the middleware before contextvar reset),
            # fall back to the active contextvar for loggers without an extra.
            "request_id": getattr(record, "request_id", None) or get_request_id(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key in ("method", "path", "status_code", "duration_ms", "user_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Remove only handlers this function installed before, so re-entry is
    # idempotent without detaching handlers owned by the host process
    # (pytest caplog, uvicorn, ...).
    for existing in list(root.handlers):
        if isinstance(existing, logging.StreamHandler) and isinstance(
            existing.formatter, JsonFormatter
        ):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())
