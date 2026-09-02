# S0 — Nền tảng & Hạ tầng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the full monorepo for the AI customer-support system: git, backend (FastAPI async) + frontend (React/Vite) skeletons, all 11 DB tables via Alembic, idempotent seed, health endpoints, and Docker Compose that boots the whole stack green.

**Architecture:** Monorepo `backend/` (FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic) and `frontend/` (React 18 + Vite + Vanilla CSS). PostgreSQL 16 runs in Docker. Backend container runs `alembic upgrade head → seed → uvicorn` on boot. Frontend (production) served by nginx proxying `/api` to backend; during dev run Vite with its own proxy.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Alembic, pydantic-settings, bcrypt, pytest + pytest-asyncio + httpx; React 18, Vite; PostgreSQL 16, Docker Compose.

## Global Constraints

These come verbatim from the approved spec (`docs/superpowers/specs/2026-09-02-ai-customer-support-design.md`) and SRS (`documents/SRS.md`). Every task's code must satisfy them:

- Stack FIXED: React + Vite + Vanilla CSS (NO Tailwind) · FastAPI + Pydantic · PostgreSQL + SQLAlchemy · Gemini API · JWT/bcrypt · Docker Compose.
- All 11 tables implemented per SRS §6.3 with **exact column names, nullability, types** from the data dictionaries; indexes per §6.5.
- All timestamps `TIMESTAMPTZ` (UTC); store as `DateTime(timezone=True)` + `server_default=func.now()`.
- Every PK is a UUID (Python-side `default=uuid.uuid4`).
- No state "Assigned" (SRS §16); assignment is columns `team_id`/`assigned_to`.
- Backend is the security boundary (SRS §16): no business logic trusts the frontend.
- Frontend UI language: **Vietnamese**; identifiers/enums in English.
- `.env` never committed; project ships `.env.example` without secrets (§14.1).
- Initial passwords are NOT hard-coded (§14.3): passed via env (`SEED_ADMIN_PASSWORD`).
- Seed must be **idempotent**: safe to run on every container start; never wipes data (§14.3).
- Health endpoints per §14.2: `/health/live` (process), `/health/ready` (DB reachable + migration applied), `/health/ai` (AI status — reported separately; AI failure must NOT fail liveness).
- Every business record uses timezone-aware timestamps; no naive datetime columns.
- Host shell: this machine is Windows with Git-Bash available. **All commands below run inside Docker containers or through `docker compose exec`**, so they are identical cross-platform — do not activate Python venvs on the host for running the stack.

---

### Task 0: Initialize git repository and baseline docs

**Files:**
- Create: `.gitignore`
- (docs/superpowers/specs/... and documents/ already exist on disk, uncommitted)

**Interfaces:** none yet.

- [ ] **Step 1: Check current git status**

Run: `git -C "D:/DuAm/HeThongHoTroAI" rev-parse --is-inside-work-tree`
Expected: `fatal: not a git repository` (project is not yet under git).

- [ ] **Step 2: Create `.gitignore`**

Create file `D:/DuAm/HeThongHoTroAI/.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
.python-version

# Node / frontend
node_modules/
frontend/dist/
frontend/.vite/
*.local

# Environment & secrets — real .env is never committed
.env
.env.*
!.env.example

# Docker data (never commit a DB volume)
pgdata/

# Editors / OS
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db

# Logs
*.log
```

- [ ] **Step 3: Initialize git, set a local identity, and commit baseline**

Set a repo-local author identity (this machine may not have a global git identity; the local one makes later plain `git commit` calls work). Use the project authors from the spec.

Run:
```bash
cd "D:/DuAm/HeThongHoTroAI"
git init -b main
git config user.name "La Van Tuan"
git config user.email "tuantv@example.com"
git add .gitignore documents docs
git commit -m "chore: baseline SRS and design spec

Co-Authored-By: Claude <noreply@anthropic.com>"
```
Expected: commit succeeds listing `documents/SRS.md`, the spec file, and `.gitignore`.

- [ ] **Step 4: Verify clean tree + identity persisted**

Run:
```bash
git status --porcelain
git config user.name
```
Expected: empty output from the first command; `La Van Tuan` printed by the second.

---

### Task 1: Backend skeleton + config + structured logging

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/core/middleware.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/unit/test_config.py`
- Create: `backend/tests/unit/test_middleware.py`

**Interfaces:**
- Consumes: nothing yet.
- Produces:
  - `get_settings() -> Settings` (lru_cached) in `app.core.config`.
  - `configure_logging(level: str) -> None`, `get_request_id() -> str` in `app.core.logging`.
  - ASGI middleware `RequestContextMiddleware` in `app.core.middleware`.

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-support-backend"
version = "0.1.0"
description = "Customer-support system with AI (backend)"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "bcrypt>=4.1",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: requires a live PostgreSQL (docker compose up -d db)",
]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `backend/.dockerignore`**

```
__pycache__/
*.py[cod]
.pytest_cache/
tests/
.venv/
```

- [ ] **Step 3: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

# Editable install: the compose bind-mount ./backend:/app then shadows /app with
# live host code, and -e keeps site-packages pointing at /app/app — so uvicorn
# picks up edits without a rebuild. (A plain `pip install .` would freeze the
# built copy in site-packages and stale the dev loop.)
RUN pip install --no-cache-dir -e . ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: `tests/` is excluded from the image, but a bind-mount of `./backend:/app` in docker-compose re-adds it during development, so `docker compose exec backend pytest` works (Task 6).

- [ ] **Step 4: Create `backend/app/__init__.py`**

```python
"""AI customer-support backend package."""
```

- [ ] **Step 5: Create `backend/app/core/__init__.py`**

```python
"""Core infrastructure: config, logging, security, middleware."""
```

- [ ] **Step 6: Create `backend/app/core/config.py`**

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "AI Customer Support"
    environment: str = "development"
    log_level: str = "INFO"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )

    # Database
    database_url: str = (
        "postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support"
    )

    # Auth (used from S1 onward; keep defaults so S0 boots)
    jwt_secret_key: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False

    # AI provider (real use from S4 onward)
    ai_provider: str = "mock"  # "gemini" | "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    ai_timeout_seconds: int = 30
    ai_low_confidence_threshold: float = 0.70

    # Uploads (real use from S2 onward)
    max_upload_size_mb: int = 10
    allowed_file_types: str = "pdf,png,jpg,jpeg,txt,docx"

    # Seed admin (created from Task 5 onward)
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = ""  # must be provided via env, never hard-coded


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Create `backend/app/core/logging.py`**

```python
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
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
```

- [ ] **Step 8: Create `backend/app/core/middleware.py`**

```python
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import configure_logging, request_id_var

access_logger = logging.getLogger("app.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request_id, expose it as a response header, and log an access line."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Reraise; global exception handler (added later) formats the error body.
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        access_logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
```

- [ ] **Step 9: Create test package + conftest**

`backend/tests/__init__.py`:
```python
```

`backend/tests/conftest.py`:
```python
import os

import pytest

# Disable .env loading for tests so results are deterministic.
os.environ.setdefault("AI_PROVIDER", "mock")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 10: Write failing tests**

`backend/tests/unit/test_config.py`:
```python
from app.core.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 7
    assert s.ai_low_confidence_threshold == 0.70
    assert s.max_upload_size_mb == 10
    assert "ai_support" in s.database_url
```

`backend/tests/unit/test_middleware.py`:
```python
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
```

- [ ] **Step 11: Create a local venv and install the package in editable mode**

The container install (for the running stack) happens in Task 6; this host venv is only so pytest can run unit tests quickly on Windows.

Windows Git-Bash:
```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: install completes. The editable install makes the `app` package importable from the `backend/` directory.

- [ ] **Step 12: Run tests to verify they pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: PASS (3 tests: 1 config + 2 middleware).

TDD note for this task: the units under test are brand-new scaffolding with no pre-existing behavior, so the red phase is exercised per-file during authoring (an import of a module you forgot to create fails loudly). The behavior contracts are the assertions above; later tasks that add behavior on top of these files MUST write their failing test first.

- [ ] **Step 14: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend
git commit -m "chore(backend): scaffold fastapi app with config and request-id logging

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: SQLAlchemy base, enums, and all 11 ORM models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/enums.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/team.py`
- Create: `backend/app/models/ticket.py`
- Create: `backend/app/models/audit.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/session.py`
- Test: `backend/tests/unit/test_models.py`

**Interfaces:**
- Consumes: `Settings` from Task 1 (`app.core.config`).
- Produces:
  - `Base` (DeclarativeBase with naming convention) in `app.models.base`.
  - Enums: `UserRole, TeamRole, TicketStatus, TicketPriority, TicketCategory, Visibility, CommentSource, AiResultType, AiStatus, AuditOutcome` in `app.models.enums`.
  - Tables (SQLAlchemy model classes): `User, RefreshToken` (user.py); `SupportTeam, TeamMember` (team.py); `SlaPolicy, Ticket, AiResult, Comment, Attachment, TicketHistory` (ticket.py); `AuditLog` (audit.py).
  - `engine` (async) and `AsyncSessionLocal` in `app.db.session`.

- [ ] **Step 1: Write failing metadata test**

`backend/tests/unit/test_models.py`:
```python
def _expected_tables():
    return {
        "users", "support_teams", "team_members", "tickets", "comments",
        "attachments", "ai_results", "ticket_history", "sla_policies",
        "refresh_tokens", "audit_logs",
    }


def test_models_module_registers_all_11_tables():
    import app.models  # noqa: F401  (import registers all tables)

    from app.models.base import Base

    assert set(Base.metadata.tables.keys()) == _expected_tables()


def test_tickets_has_required_columns():
    import app.models  # noqa: F401

    from app.models.base import Base

    cols = set(Base.metadata.tables["tickets"].columns.keys())
    required = {
        "id", "ticket_code", "requester_name", "requester_email", "subject",
        "description", "category", "priority", "status", "team_id",
        "assigned_to", "sla_policy_id", "first_response_due_at",
        "resolution_due_at", "first_response_at", "resolved_at", "closed_at",
        "version", "created_at", "updated_at", "archived_at",
    }
    assert required <= cols
```

- [ ] **Step 2: Verify it fails**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Create `app/models/__init__.py`**

```python
# Import every model module so that Base.metadata is fully populated.
from . import audit, team, ticket, user  # noqa: F401
```

- [ ] **Step 4: Create `app/models/enums.py`**

```python
from enum import Enum


class UserRole(str, Enum):
    AGENT = "AGENT"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class TeamRole(str, Enum):
    MEMBER = "MEMBER"
    MANAGER = "MANAGER"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    ACCOUNT = "ACCOUNT"
    BILLING = "BILLING"
    GENERAL = "GENERAL"
    OTHER = "OTHER"


class Visibility(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class CommentSource(str, Enum):
    HUMAN = "HUMAN"
    AI_ASSISTED = "AI_ASSISTED"


class AiResultType(str, Enum):
    CLASSIFICATION = "CLASSIFICATION"
    SUMMARY = "SUMMARY"
    DRAFT_REPLY = "DRAFT_REPLY"


class AiStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AuditOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
```

- [ ] **Step 5: Create `app/models/base.py`**

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

- [ ] **Step 6: Create `app/models/user.py`**

Columns per SRS §6.3.1 (users) and §6.3.10 (refresh_tokens).

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.models.base import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(100), nullable=False)
    # unique=True => DB unique constraint (its implicit index serves email lookups).
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        type_=String(30), nullable=False, default=UserRole.AGENT.value
    )  # validated at Pydantic layer; values: AGENT/MANAGER/ADMIN
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    failed_login_count = Column(Integer, nullable=False, server_default=text("0"))
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    refresh_tokens = relationship("RefreshToken", back_populates="user")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_agent = Column(Text, nullable=True)
    ip_address = Column(INET, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")
```

- [ ] **Step 7: Create `app/models/team.py`**

Columns per SRS §6.3.2 (support_teams) and §6.3.3 (team_members). `team_members(team_id, user_id)` unique per §6.3.3 and §6.5.

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.models.base import Base


class SupportTeam(Base):
    __tablename__ = "support_teams"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    members = relationship("TeamMember", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(
        Uuid(as_uuid=True), ForeignKey("support_teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    team_role = Column(String(30), nullable=False)  # MEMBER | MANAGER
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    team = relationship("SupportTeam", back_populates="members")
    user = relationship("User")
```

- [ ] **Step 8: Create `app/models/ticket.py`**

Columns per SRS §6.3.4..§6.3.9, indexes per §6.5. All enums are stored as `VARCHAR(30)` (DB-enforced valid values come from the Pydantic layer); this keeps Alembic migrations simple and is SRS-compatible ("VARCHAR(50) hoặc FK" for category, ENUM → our typed string columns validated above ORM).

```python
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.models.base import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    priority = Column(String(30), nullable=False)  # LOW/MEDIUM/HIGH/URGENT
    first_response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    pause_on_pending = Column(Boolean, nullable=False, server_default=text("false"))
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint(
            "first_response_minutes > 0",
            name="sla_first_response_positive",
        ),
        CheckConstraint(
            "resolution_minutes > 0",
            name="sla_resolution_positive",
        ),
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_updated", "status", "updated_at"),
        Index("ix_tickets_team_status_updated", "team_id", "status", "updated_at"),
        Index("ix_tickets_assigned_status_updated", "assigned_to", "status", "updated_at"),
        Index("ix_tickets_priority_resolution_due", "priority", "resolution_due_at"),
        Index("ix_tickets_requester_email", "requester_email"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique constraint (implicit unique index) satisfies SRS 6.5 tickets(ticket_code).
    ticket_code = Column(String(30), nullable=False, unique=True)
    requester_name = Column(String(100), nullable=False)
    requester_email = Column(String(255), nullable=False)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)  # TECHNICAL/ACCOUNT/BILLING/GENERAL/OTHER
    priority = Column(String(30), nullable=False)  # LOW/MEDIUM/HIGH/URGENT
    status = Column(String(30), nullable=False)  # OPEN/IN_PROGRESS/PENDING/RESOLVED/CLOSED
    team_id = Column(
        Uuid(as_uuid=True), ForeignKey("support_teams.id"), nullable=True, index=True
    )
    assigned_to = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    sla_policy_id = Column(
        Uuid(as_uuid=True), ForeignKey("sla_policies.id"), nullable=True
    )
    first_response_due_at = Column(DateTime(timezone=True), nullable=True)
    resolution_due_at = Column(DateTime(timezone=True), nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    comments = relationship("Comment", back_populates="ticket", lazy="selectin")
    attachments = relationship("Attachment", back_populates="ticket", lazy="selectin")
    history = relationship("TicketHistory", back_populates="ticket", lazy="selectin")
    ai_results = relationship("AiResult", back_populates="ticket", lazy="selectin")


class AiResult(Base):
    __tablename__ = "ai_results"
    __table_args__ = (
        Index(
            "ix_ai_results_ticket_type_status_requested",
            "ticket_id",
            "result_type",
            "status",
            "requested_at",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    requested_by = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    result_type = Column(String(30), nullable=False)  # CLASSIFICATION/SUMMARY/DRAFT_REPLY
    status = Column(String(30), nullable=False)  # PENDING_REVIEW/APPROVED/EDITED/REJECTED/FAILED
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(30), nullable=False)
    input_hash = Column(String(128), nullable=False)
    context_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    original_output = Column(JSONB, nullable=True)
    reviewed_output = Column(JSONB, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    reviewer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_reason = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)

    ticket = relationship("Ticket", back_populates="ai_results")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_ticket_created", "ticket_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    visibility = Column(String(30), nullable=False)  # PUBLIC/INTERNAL
    source = Column(String(30), nullable=False)  # HUMAN/AI_ASSISTED
    ai_result_id = Column(
        Uuid(as_uuid=True), ForeignKey("ai_results.id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    comment_id = Column(
        Uuid(as_uuid=True), ForeignKey("comments.id"), nullable=True
    )
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False, unique=True)
    storage_path = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum = Column(String(128), nullable=True)
    uploaded_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", back_populates="attachments")


class TicketHistory(Base):
    __tablename__ = "ticket_history"
    __table_args__ = (
        Index("ix_ticket_history_ticket_created", "ticket_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    changed_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # STATUS_CHANGED/ASSIGNED/FIELD_UPDATED/...
    field_name = Column(String(50), nullable=True)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    ticket = relationship("Ticket", back_populates="history")
```

- [ ] **Step 9: Create `app/models/audit.py`**

Columns per SRS §6.3.11 + §6.5 indexes.

```python
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.types import Uuid

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Uuid(as_uuid=True), nullable=True)
    outcome = Column(String(30), nullable=False)  # SUCCESS/FAILURE
    # "metadata" is a reserved Base attribute name, so expose it as metadata_ mapped to column "metadata".
    metadata_ = Column("metadata", JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 10: Create `app/db/session.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
```

Create `app/db/__init__.py`:
```python
"""Database engine, session, and seed."""
```

- [ ] **Step 11: Verify metadata test passes**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_models.py -q`
Expected: PASS (2 tests).

- [ ] **Step 12: Run whole unit suite**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: PASS (5 tests: 3 from Task 1 + 2 models).

- [ ] **Step 13: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/models backend/app/db backend/tests/unit/test_models.py
git commit -m "feat(backend): add 11-table ORM model layer per SRS 6.3

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Alembic async migrations + health API + app factory

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/unit/test_health.py`

**Interfaces:**
- Consumes: `Base` metadata (Task 2), `Settings` (Task 1), `configure_logging` (Task 1).
- Produces: FastAPI instance factory `create_app()` in `app.main`; `app` module-level instance. Routers mounted under `/health` (`/live`, `/ready`, `/ai`).

- [ ] **Step 1: Write failing health test**

`backend/tests/unit/test_health.py`:
```python
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
```

- [ ] **Step 2: Verify failure**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_health.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Create `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
# sqlalchemy.url is injected from Settings in alembic/env.py (never hard-code here)
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Create `backend/alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings

# Import models so metadata is fully populated.
from app.models import audit, team, ticket, user  # noqa: F401
from app.models.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _db_url() -> str:
    url = get_settings().database_url
    # Alembic treats % in config as interpolation markers; escape any literal %.
    return url.replace("%", "%%")


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # Set the URL BEFORE building the engine (the engine reads the config section).
    config.set_main_option("sqlalchemy.url", _db_url())
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations)
    await connectable.dispose()


def run_migrations_offline_entry() -> None:
    run_migrations_offline()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline_entry()
else:
    run_migrations_online()
```

- [ ] **Step 5: Create `backend/alembic/script.py.mako`**

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Create the app factory, health router, package markers**

`backend/app/api/__init__.py`:
```python
"""HTTP routers."""
```

`backend/app/api/health.py`:
```python
from fastapi import APIRouter, Response, status
from sqlalchemy import text

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
        # Deep reachability probe is implemented in S4 (AI engine).
        return {"status": "ok", "provider": settings.ai_provider, "probe": "deferred"}
    return {"status": "ok", "provider": settings.ai_provider}
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # RequestContextMiddleware added last => runs first (outermost).
    application.add_middleware(RequestContextMiddleware)

    # Serve health at both prefixes: /health (direct probes) and /api/health
    # (same path survives the frontend nginx proxy_pass /api -> backend:8000).
    application.include_router(health_router, prefix="/health")
    application.include_router(health_router, prefix="/api/health")

    return application


app = create_app()
```

- [ ] **Step 7: Create `.gitkeep` for versions dir**

`backend/alembic/versions/.gitkeep`: empty file.

- [ ] **Step 8: Run health tests**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: PASS (8 tests: 5 from Task 2 + 3 health). The readiness test monkeypatches the engine to a dead port, so it is deterministic and does not require knowing whether Postgres is running.

- [ ] **Step 9: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/alembic backend/app/api backend/app/main.py backend/tests/unit/test_health.py
git commit -m "feat(backend): async alembic env and health endpoints (live/ready/ai)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Security helpers (bcrypt) used by seed

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/unit/test_security.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`, `generate_ticket_code() -> str` (used by seed + later ticket core).

- [ ] **Step 1: Write failing tests**

`backend/tests/unit/test_security.py`:
```python
import bcrypt

from app.core.security import generate_ticket_code, hash_password, verify_password


def test_hash_and_verify_roundtrip():
    hashed = hash_password("S3cret!pw")
    assert hashed.startswith("$2b$")
    assert verify_password("S3cret!pw", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_generate_ticket_code_shape():
    code = generate_ticket_code()
    assert code.startswith("TK-")
    assert len(code) == 11  # "TK-" + 8 chars
    assert code[3:].isalnum()
    assert code == code.upper()
```

- [ ] **Step 2: Verify failure**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_security.py -q`
Expected: FAIL — import error for `app.core.security`.

- [ ] **Step 3: Implement `app/core/security.py`**

```python
import base64
import os
import secrets

import bcrypt


def hash_password(plain: str) -> str:
    # bcrypt only reads the first 72 bytes; raise early rather than silently truncate.
    if len(plain.encode("utf-8")) > 72:
        raise ValueError("password longer than 72 bytes is not supported")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # base32, no 0/O/1/I


def generate_ticket_code() -> str:
    """Public, hard-to-guess ticket code: 'TK-' + 8 base32 chars (SRS BR-01)."""
    raw = secrets.token_bytes(8)
    n = int.from_bytes(raw, "big")
    chars: list[str] = []
    for _ in range(8):
        n, rem = divmod(n, 32)
        chars.append(_ALPHABET[rem])
    return "TK-" + "".join(chars)
```

- [ ] **Step 4: Run security tests**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_security.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/core/security.py backend/tests/unit/test_security.py
git commit -m "feat(backend): bcrypt password helpers and ticket-code generator

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Idempotent seed (admin + teams + SLA + sample tickets)

**Files:**
- Create: `backend/app/db/seed.py`
- Test: `backend/tests/integration/test_seed.py` (marked `integration`, requires live Postgres)

**Interfaces:**
- Consumes: all models (Task 2), `AsyncSessionLocal` (Task 2), `hash_password`, `generate_ticket_code` (Task 4), `Settings` (Task 1).
- Produces: `async def run_seed(session_factory=AsyncSessionLocal) -> None` — idempotent.

- [ ] **Step 1: Write the integration test (failing first)**

`backend/tests/integration/test_seed.py`:
```python
import os

import pytest

from app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("INTEGRATION", ""),
    reason="set INTEGRATION=1 when a live Postgres (docker compose up -d db) is available",
)
async def test_seed_is_idempotent(anyio_backend):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import AsyncSession

    import app.db.seed as seed_mod
    from app.models.team import SupportTeam
    from app.models.ticket import SlaPolicy, Ticket
    from app.models.user import User

    # Point an engine at the real DB for this run (migrations must already be applied).
    engine = create_async_engine(Settings().database_url)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Run seed twice; counts must be identical the second time (idempotent).
    await seed_mod.run_seed(factory)
    first = await _counts(engine)
    await seed_mod.run_seed(factory)
    second = await _counts(engine)
    assert first == second, "seed must be idempotent"

    async with factory() as session:
        assert (await session.execute(select(func.count()).select_from(User))).scalar_one() >= 1
        assert (await session.execute(select(func.count()).select_from(SupportTeam))).scalar_one() == 2
        assert (await session.execute(select(func.count()).select_from(SlaPolicy))).scalar_one() == 4
        assert (await session.execute(select(func.count()).select_from(Ticket))).scalar_one() >= 6

    await engine.dispose()


async def _counts(engine):
    from sqlalchemy import text

    out = {}
    async with engine.connect() as conn:
        for tbl in ("users", "support_teams", "team_members", "tickets",
                    "sla_policies", "ai_results"):
            out[tbl] = (await conn.execute(text(f"SELECT count(*) FROM {tbl}"))).scalar_one()
    return out
```

- [ ] **Step 2: Implement `app/db/seed.py`**

```python
"""Idempotent initial data (SRS 14.3). Safe to run on every boot; never deletes data."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.enums import (
    AiResultType,
    AiStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    TeamRole,
    UserRole,
)
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import AiResult, SlaPolicy, Ticket
from app.models.user import User

logger = logging.getLogger(__name__)

# Non-secret sample content only; no customer PII in seed.
_TEAM_SPECS = [
    {
        "name": "Team Kỹ thuật",
        "manager": ("Nguyễn Văn Hùng", "hung.manager@example.com"),
        "agents": [
            ("Trần Thị Lan", "lan.agent@example.com"),
            ("Lê Văn Minh", "minh.agent@example.com"),
        ],
    },
    {
        "name": "Team Tài khoản & Thanh toán",
        "manager": ("Phạm Thu Hà", "ha.manager@example.com"),
        "agents": [
            ("Hoàng Văn Đạt", "dat.agent@example.com"),
            ("Vũ Thị Ngọc", "ngoc.agent@example.com"),
        ],
    },
]

_SLA_MINUTES = {
    TicketPriority.URGENT.value: (15, 240),
    TicketPriority.HIGH.value: (60, 480),
    TicketPriority.MEDIUM.value: (240, 1440),
    TicketPriority.LOW.value: (480, 2880),
}

_SAMPLE_TICKETS = [
    {
        "subject": "Không đăng nhập được vào tài khoản",
        "requester_name": "Mai Văn Sơn",
        "requester_email": "son.customer@example.com",
        "priority": TicketPriority.HIGH.value,
        "category": TicketCategory.ACCOUNT.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.IN_PROGRESS.value,
    },
    {
        "subject": "Website chậm khi truy cập buổi sáng",
        "requester_name": "Đỗ Thu Trang",
        "requester_email": "trang.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.TECHNICAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.OPEN.value,
    },
    {
        "subject": "Hóa đơn tháng 8 bị tính sai phí",
        "requester_name": "Ngô Văn Khải",
        "requester_email": "khai.customer@example.com",
        "priority": TicketPriority.URGENT.value,
        "category": TicketCategory.BILLING.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.PENDING.value,
    },
    {
        "subject": "Hướng dẫn xuất báo cáo doanh thu",
        "requester_name": "Trịnh Thu Hương",
        "requester_email": "huong.customer@example.com",
        "priority": TicketPriority.LOW.value,
        "category": TicketCategory.GENERAL.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.RESOLVED.value,
    },
    {
        "subject": "Lỗi không tải được file đính kèm",
        "requester_name": "Lý Văn Thành",
        "requester_email": "thanh.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.TECHNICAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.OPEN.value,
    },
    {
        "subject": "Câu hỏi về gói dịch vụ Premium",
        "requester_name": "Đinh Thu Vân",
        "requester_email": "van.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.GENERAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.CLOSED.value,
    },
]


async def run_seed(session_factory: async_sessionmaker | None = None) -> None:
    settings = get_settings()
    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        admin = await _ensure_admin(session, settings)
        team_by_name: dict[str, SupportTeam] = {}
        user_by_email: dict[str, User] = {admin.email: admin}

        for spec in _TEAM_SPECS:
            team, mgr = await _ensure_team(session, spec, user_by_email)
            team_by_name[spec["name"]] = team

        sla_by_priority: dict[str, SlaPolicy] = await _ensure_sla_policies(session)

        await _ensure_tickets(
            session, _SAMPLE_TICKETS, team_by_name, user_by_email, sla_by_priority
        )

        await session.commit()
    logger.info("seed complete")


async def _ensure_admin(session: AsyncSession, settings) -> User:
    existing = (
        await session.execute(select(User).where(User.email == settings.seed_admin_email.lower()))
    ).scalar_one_or_none()
    if existing:
        return existing
    if not settings.seed_admin_password:
        raise RuntimeError("SEED_ADMIN_PASSWORD must be provided via env (SRS 14.3)")
    admin = User(
        full_name="Quản trị viên hệ thống",
        email=settings.seed_admin_email.lower(),
        password_hash=hash_password(settings.seed_admin_password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    logger.info("seeded admin %s", admin.email)
    return admin


async def _ensure_team(session: AsyncSession, spec: dict, user_by_email: dict) -> tuple[SupportTeam, User]:
    team = (
        await session.execute(select(SupportTeam).where(SupportTeam.name == spec["name"]))
    ).scalar_one_or_none()
    if team is None:
        team = SupportTeam(name=spec["name"], description=spec["name"])
        session.add(team)
        await session.flush()

    mgr_email, agents = spec["manager"][1].lower(), spec["agents"]
    mgr = user_by_email.get(mgr_email)
    if mgr is None:
        mgr = User(
            full_name=spec["manager"][0],
            email=mgr_email,
            password_hash=hash_password(f"{mgr_email.split('@')[0]}@Dev123"),
            role=UserRole.MANAGER.value,
            is_active=True,
        )
        session.add(mgr)
        await session.flush()
        user_by_email[mgr_email] = mgr

    await _ensure_membership(session, team.id, mgr.id, TeamRole.MANAGER.value)

    for full_name, email in agents:
        email = email.lower()
        agent = user_by_email.get(email)
        if agent is None:
            agent = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(f"{email.split('@')[0]}@Dev123"),
                role=UserRole.AGENT.value,
                is_active=True,
            )
            session.add(agent)
            await session.flush()
            user_by_email[email] = agent
        await _ensure_membership(session, team.id, agent.id, TeamRole.MEMBER.value)

    return team, mgr


async def _ensure_membership(session: AsyncSession, team_id, user_id, team_role: str) -> None:
    existing = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    session.add(TeamMember(team_id=team_id, user_id=user_id, team_role=team_role, is_active=True))
    await session.flush()


async def _ensure_sla_policies(session: AsyncSession) -> dict[str, SlaPolicy]:
    by_priority: dict[str, SlaPolicy] = {}
    for priority, (fr, res) in _SLA_MINUTES.items():
        existing = (
            await session.execute(select(SlaPolicy).where(SlaPolicy.priority == priority))
        ).scalars().all()
        policy = existing[0] if existing else SlaPolicy(
            name=f"SLA {priority}",
            priority=priority,
            first_response_minutes=fr,
            resolution_minutes=res,
            pause_on_pending=False,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            is_active=True,
        )
        if not existing:
            session.add(policy)
            await session.flush()
        by_priority[priority] = policy
    return by_priority


async def _ensure_tickets(session, samples, team_by_name, user_by_email, sla_by_priority) -> None:
    from app.models.user import User as _User

    # Deterministic ticket codes so repeated seeds are idempotent.
    for i, sample in enumerate(samples, start=1):
        code = f"TK-DEMO{i:04d}"  # demo codes; real codes come from generate_ticket_code()
        existing = (
            await session.execute(select(Ticket).where(Ticket.ticket_code == code))
        ).scalar_one_or_none()
        if existing:
            continue
        team = team_by_name[sample["team_name"]]
        # First active member of the team becomes the assignee for demo tickets.
        member_row = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id, TeamMember.is_active.is_(True)
                ).limit(1)
            )
        ).scalar_one_or_none()
        assignee = None
        if member_row is not None:
            assignee = (
                await session.execute(select(_User).where(_User.id == member_row.user_id))
            ).scalar_one_or_none()

        sla = sla_by_priority[sample["priority"]]
        ticket = Ticket(
            ticket_code=code,
            requester_name=sample["requester_name"],
            requester_email=sample["requester_email"],
            subject=sample["subject"],
            description=f"Nội dung mẫu cho ticket {code}.",
            category=sample["category"],
            priority=sample["priority"],
            status=sample["status"],
            team_id=team.id,
            assigned_to=assignee.id if assignee else None,
            sla_policy_id=sla.id,
            version=1,
        )
        session.add(ticket)
        await session.flush()

        if i == 3 and assignee is not None:
            # One pending-review AI classification sample per spec (S0 deliverable).
            # requested_by is NOT NULL, so we only insert when an assignee exists.
            session.add(
                AiResult(
                    ticket_id=ticket.id,
                    requested_by=assignee.id,
                    result_type=AiResultType.CLASSIFICATION.value,
                    status=AiStatus.PENDING_REVIEW.value,
                    model_name="seed-mock",
                    prompt_version="classify-v1",
                    input_hash="seed-sample-hash",
                    confidence=0.92,
                    original_output={
                        "category": sample["category"],
                        "priority": sample["priority"],
                        "confidence": 0.92,
                        "reason": "Mẫu seed.",
                    },
                )
            )
```

- [ ] **Step 3: Generate the initial Alembic migration**

Bring up the database first (Task 6 defines the exact compose file, but a one-off DB container is enough here):

```bash
cd "D:/DuAm/HeThongHoTroAI"
docker run -d --name ai_support_db \
  -e POSTGRES_USER=ai_support -e POSTGRES_PASSWORD=ai_support -e POSTGRES_DB=ai_support \
  -p 5432:5432 -v ai_support_pgdata:/var/lib/postgresql/data postgres:16-alpine
docker exec ai_support_db pg_isready -U ai_support -d ai_support
```
Expected: `... accepting connections`.

Then inside backend (host venv) generate the migration:
```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
.venv/Scripts/python -m alembic revision --autogenerate -m "initial schema: 11 tables"
```
Expected: writes `alembic/versions/<hash>_initial_schema_11_tables.py`. Review it: it must `create_table` for all 11 tables and the `CREATE INDEX`/`UNIQUE` statements from the models.

- [ ] **Step 4: Apply migration and run seed**

```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support" \
SEED_ADMIN_PASSWORD="Admin@Dev123" \
.venv/Scripts/python -m alembic upgrade head
```
Expected: `Running upgrade ... -> <rev>, initial schema: 11 tables`.

Run seed manually once:
```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support" \
SEED_ADMIN_PASSWORD="Admin@Dev123" \
.venv/Scripts/python -c "import asyncio; from app.db.seed import run_seed; asyncio.run(run_seed())"
```
Expected: logs `seed complete`; no error on second run (idempotent).

- [ ] **Step 5: Run the integration test (with INTEGRATION=1)**

```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support" \
INTEGRATION=1 SEED_ADMIN_PASSWORD="Admin@Dev123" \
.venv/Scripts/python -m pytest tests/integration -q
```
Expected: PASS (1 test). 

Then stop the one-off DB:
```bash
docker rm -f ai_support_db
```

- [ ] **Step 6: Commit migration + seed + test**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/alembic/versions backend/app/db/seed.py backend/tests/integration
git commit -m "feat(backend): initial migration and idempotent seed

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Docker Compose (db + backend + frontend) and env template

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Create: `frontend/src/api/client.js`
- Create: `README.md`

**Interfaces:**
- Consumes: `backend/app/main.py` (`app` object), Task 5 migration+seed.
- Produces: one command `docker compose up --build` boots db+backend+frontend green; frontend at `http://localhost:8080`, backend docs at `http://localhost:8000/api/docs`.

- [ ] **Step 1: Write `.env.example`**

```env
# Copy to .env and fill secrets. Never commit .env (SRS 14.1).

# --- Database ---
POSTGRES_USER=ai_support
POSTGRES_PASSWORD=ai_support
POSTGRES_DB=ai_support
# URL used by the backend inside the compose network:
DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@db:5432/ai_support
# URL for running host-side tests against the exposed port 5432:
DATABASE_URL_HOST=postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support

# --- Auth (secret!) ---
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET_KEY=change-me-please

# --- Seed admin (secret!, SRS 14.3 — never hard-coded) ---
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=Admin@Dev123

# --- AI (secret when provider=gemini) ---
AI_PROVIDER=mock
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

# --- General ---
LOG_LEVEL=INFO
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8080
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
name: ai-customer-support

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-ai_support}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-ai_support}
      POSTGRES_DB: ${POSTGRES_DB:-ai_support}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-ai_support} -d ${POSTGRES_DB:-ai_support}"]
      interval: 5s
      timeout: 5s
      retries: 10

  backend:
    build: ./backend
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-ai_support}:${POSTGRES_PASSWORD:-ai_support}@db:5432/${POSTGRES_DB:-ai_support}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-dev-insecure-secret-change-me}
      SEED_ADMIN_EMAIL: ${SEED_ADMIN_EMAIL:-admin@example.com}
      SEED_ADMIN_PASSWORD: ${SEED_ADMIN_PASSWORD}
      AI_PROVIDER: ${AI_PROVIDER:-mock}
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
      GEMINI_MODEL: ${GEMINI_MODEL:-gemini-2.0-flash}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS:-http://localhost:5173,http://localhost:8080}
    command: >
      sh -c "alembic upgrade head &&
             python -m app.db.seed &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"
    volumes:
      - ./backend:/app
      # Hide the host's Windows .venv (irrelevant and large inside the container).
      - /app/.venv
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 3: Write frontend production files**

`frontend/Dockerfile`:
```dockerfile
# ---- build stage ----
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# ---- serve stage ----
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API to the backend container
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`frontend/.dockerignore`:
```
node_modules
dist
.vite
```

`frontend/package.json`:
```json
{
  "name": "ai-support-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.0"
  }
}
```

`frontend/vite.config.js`:
```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server proxies /api and /health to the backend (single origin => cookies work).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Hệ thống hỗ trợ khách hàng</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/src/main.jsx`:
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './styles/tokens.css';
import './styles/base.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`frontend/src/styles/tokens.css` (design tokens — Vanilla CSS per stack constraint):
```css
:root {
  --color-bg: #ffffff;
  --color-surface: #f7f9fc;
  --color-border: #dbe1ea;
  --color-text: #1a2433;
  --color-text-muted: #5c6b80;
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-danger: #dc2626;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-6: 24px; --space-8: 32px;
  --font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.25rem;
  --shadow-sm: 0 1px 2px rgba(16, 24, 40, 0.06);
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #0f172a;
    --color-surface: #1e293b;
    --color-border: #334155;
    --color-text: #e2e8f0;
    --color-text-muted: #94a3b8;
  }
}
```

`frontend/src/styles/base.css`:
```css
* { box-sizing: border-box; }
html, body, #root { height: 100%; }
body {
  margin: 0;
  font-family: var(--font-family);
  font-size: var(--font-size-base);
  color: var(--color-text);
  background: var(--color-bg);
  line-height: 1.5;
}
a { color: var(--color-primary); }
```

`frontend/src/api/client.js`:
```js
// Minimal fetch wrapper; auth + 401-refresh added in slice S1.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.message || `HTTP ${res.status}`);
    err.status = res.status;
    err.error_code = body.error_code;
    throw err;
  }
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data) }),
};

export { request };
```

`frontend/src/App.jsx` (S0 health dashboard — replaced by routing in S1+):
```jsx
import { useEffect, useState } from 'react';

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch('/api/health/live').then((r) => r.json()),
      fetch('/api/health/ready').then((r) => (r.ok ? r.json() : r.json().then((b) => ({ ...b, http: r.status })))),
      fetch('/api/health/ai').then((r) => (r.ok ? r.json() : r.json().then((b) => ({ ...b, http: r.status })))),
    ])
      .then(([live, ready, ai]) => setHealth({ live, ready, ai }))
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page"><p className="error">Không kết nối được backend: {error}</p></div>;
  if (!health) return <div className="page"><p>Đang kiểm tra trạng thái hệ thống…</p></div>;

  return (
    <div className="page">
      <h1>Hệ thống hỗ trợ khách hàng</h1>
      <p>Trạng thái hạ tầng (S0):</p>
      <ul className="status-list">
        <li>Liveness: <strong>{health.live?.status}</strong></li>
        <li>Readiness: <strong>{health.ready?.status}</strong>{health.ready?.message ? ` — ${health.ready.message}` : ''}</li>
        <li>AI provider: <strong>{health.ai?.provider}</strong> ({health.ai?.status})</li>
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Write `README.md` (repo root)**

```markdown
# Hệ thống hỗ trợ khách hàng có tích hợp AI

Full-stack: React + Vite + Vanilla CSS · FastAPI + SQLAlchemy (async) · PostgreSQL · Gemini API.

Yêu cầu đặc tả: [`documents/SRS.md`](documents/SRS.md). Bản thiết kế:
[`docs/superpowers/specs/2026-09-02-ai-customer-support-design.md`](docs/superpowers/specs/2026-09-02-ai-customer-support-design.md).

## Chạy toàn bộ stack (Docker)

1. `copy .env.example .env` và điền các giá trị bí mật (đặc biệt `SEED_ADMIN_PASSWORD`, `JWT_SECRET_KEY`; nếu có key Gemini thì đặt `AI_PROVIDER=gemini` và `GEMINI_API_KEY=...`).
2. `docker compose up --build`
3. Frontend: http://localhost:8080 · Backend docs: http://localhost:8000/api/docs · Health: http://localhost:8000/health/live, `/health/ready`, `/health/ai`

Backend tự chạy `alembic upgrade head` + seed (idempotent) trước khi khởi động.

## Chạy backend khi đang phát triển

- DB: `docker compose up -d db`
- Backend: `cd backend; python -m venv .venv; .venv/Scripts/python -m pip install -e ".[dev]"`
- Unit test (không cần DB): `cd backend && .venv/Scripts/python -m pytest tests/unit -q`
- Integration test (cần DB đang chạy): 
  `DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support INTEGRATION=1 .venv/Scripts/python -m pytest tests/integration -q`

## Frontend dev

`cd frontend && npm install && npm run dev` → http://localhost:5173 (proxy `/api` → backend :8000).
```

- [ ] **Step 5: Verify compose file is valid**

Run: `docker compose -f "D:/DuAm/HeThongHoTroAI/docker-compose.yml" config --quiet`
Expected: exit 0, no output.

- [ ] **Step 6: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add docker-compose.yml .env.example README.md frontend
git commit -m "chore: docker compose stack, frontend scaffold, env template, readme

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Full-stack demo + S0 acceptance

**Files:** none (verification only).

**Interfaces:** completes the S0 deliverable: `docker compose up --build` boots everything green; readiness OK.

- [ ] **Step 1: Bring the whole stack up**

```bash
cd "D:/DuAm/HeThongHoTroAI"
docker compose up --build -d
```
Expected: db healthy; backend runs `alembic upgrade head` → seed → uvicorn; frontend nginx up.

- [ ] **Step 2: Verify health endpoints**

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
curl -s http://localhost:8000/health/ai
curl -s http://localhost:8000/api/health/ready   # same router also served under /api prefix used by frontend
```
Expected: `/live` → `{"status":"ok"}`; `/ready` → `{"status":"ok","database":"ok"}`; `/ai` → `{"status":"ok","provider":"mock"}`.

- [ ] **Step 3: Verify seed data through the API surface (OpenAPI present, counts via DB)**

```bash
docker compose exec -T db psql -U ai_support -d ai_support -c \
  "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM support_teams) AS teams, (SELECT count(*) FROM tickets) AS tickets, (SELECT count(*) FROM sla_policies) AS sla;"
```
Expected: users ≥ 9, teams = 2, tickets = 6, sla = 4. (Counts exact depend on nothing else having seeded.)

- [ ] **Step 4: Verify frontend serves and proxies**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
curl -s http://localhost:8080/api/health/live
```
Expected: `200` for the page; `{"status":"ok"}` through the nginx proxy.

- [ ] **Step 5: Restart backend to prove idempotent seed**

```bash
docker compose restart backend
sleep 3
docker compose exec -T db psql -U ai_support -d ai_support -c \
  "SELECT (SELECT count(*) FROM users) AS users, (SELECT count(*) FROM tickets) AS tickets;"
```
Expected: same counts as Step 3 (seed ran again without duplicating). Backend `/health/ready` → ok.

- [ ] **Step 6: Full unit + integration suite**

```bash
cd "D:/DuAm/HeThongHoTroAI/backend"
.venv/Scripts/python -m pytest tests/unit -q
DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support" \
INTEGRATION=1 SEED_ADMIN_PASSWORD="Admin@Dev123" \
.venv/Scripts/python -m pytest tests/integration -q
```
Expected: unit PASS; integration PASS.

- [ ] **Step 7: Manual demo (recorded for the demo scenario doc in S7)**

Open http://localhost:8080 — the page shows green Liveness/Readiness and `provider: mock`. This is the S0 demo. Note: login arrives in S1.

- [ ] **Step 8: Commit any leftover fixups and tag the slice**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add -A
git status --porcelain
# If anything was fixed during the demo, commit it:
git commit -m "chore(s0): demo fixes

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-review notes (run at end of plan)

1. **Spec coverage (S0 scope):** scaffold both apps ✓ (T1, T6), docker-compose db/backend/frontend ✓ (T6), Alembic migration of all 11 tables + indexes ✓ (T3+T5 models + migration), idempotent seed admin/2 teams/SLA/6 tickets/1 AI sample ✓ (T5), `/health/live|ready|ai` ✓ (T3), request_id + structured logging ✓ (T1), `.env.example`/`.gitignore`/README ✓ (T0, T6), parse/startup smoke + health tests ✓ (T1/T3), migration-on-clean-DB ✓ (T5 Step 3-5). S1 (auth/RBAC) is deliberately NOT in this plan — it is the next slice's plan.
2. **Placeholders:** none — every step has concrete code or an exact command.
3. **Consistency:** `hash_password`/`generate_ticket_code` defined in T4 and consumed by T5; `AsyncSessionLocal` + `engine` defined T2 consumed by T3/T5; model enums stored as strings and matched by Pydantic later (noted in model docstrings).
