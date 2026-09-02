# S2 — Public Portal + Ticket core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship S2 of the AI-integrated customer-support system: a Public Portal (create + track tickets, file upload) and the internal Ticket core (scoped list/detail, field update with optimistic lock, state-machine transitions, minimal assignment, comments/notes, attachments), end to end with green tests and a runnable demo.

**Architecture:** FastAPI routers parse HTTP and call a service layer (`app/services/*`) that owns business logic, transactions, history + audit writes (design spec §5.1). Pure policy helpers (state machine, SLA math, ticket-code generation, file rules) are module-level functions so they are unit-testable without a DB. No Alembic migration is created anywhere in S2 — the S0 schema already carries every column S2 needs (verified: `tickets.first_response_at/resolved_at/closed_at/version/sla_policy_id`, `comments.visibility/source`, `attachments.*`, `ticket_history.*`, `sla_policies.*` all exist). The slice adds `slowapi` for /public rate limiting (design spec §3 decision table) and wires the remaining routers into `main.py`. The frontend adds Public Portal pages under `/` and `/track`, and replaces the ticket placeholders with a real list + detail under `/app/tickets`.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy 2.0 async + asyncpg (backend); React + Vite + Vanilla CSS + tokens.css (frontend); `slowapi` (rate limit); PostgreSQL 16 via the running compose stack (db :5433 / backend :8001 / frontend :8080).

---

## Global Constraints

Carried from the S1 plan (lines 13–32) — the project-wide base **every task inherits**:

- **Stack fixed:** FastAPI + Pydantic · PostgreSQL + SQLAlchemy async · React + Vite + **Vanilla CSS (NO Tailwind)** · JWT/bcrypt · Docker Compose. Do not add unapproved dependencies; `slowapi` is the ONE approved S2 addition (design spec §3).
- **No new Alembic migration in S2.** The S0 migration created all 11 tables incl. every S2 column. `alembic check` must stay empty at acceptance (mirrors S1).
- **Roles** are exactly `AGENT`/`MANAGER`/`ADMIN` (backend enforces RBAC + object scoping on every protected endpoint). Wrong *role* → 403 `ACCESS_DENIED`. Object outside scope → **404** `TICKET_NOT_FOUND` (anti-leak, design spec §5.1).
- **Error envelope uniform** `{error_code, message, details}`; business errors use only SRS §10.2 codes: `TICKET_NOT_FOUND`, `INVALID_STATUS_TRANSITION`, `ASSIGNEE_NOT_IN_TEAM`, `VERSION_CONFLICT`, `FILE_TOO_LARGE`, `FILE_TYPE_NOT_ALLOWED`; transport codes come from `errors._FALLBACK` (429 already maps to `RATE_LIMITED`). Never leak stack/SQL/tokens.
- **Timestamps:** `TIMESTAMPTZ` UTC stored; ISO 8601 UTC on the wire. Client converts for display.
- **Email** normalized lowercase (strip + lower) at the service boundary. Public-track mismatch and unknown code return the SAME 404 `TICKET_NOT_FOUND` message (FR-PUB-09: never confirm existence).
- **Files:** allowlist from `allowed_file_types` (`pdf,png,jpg,jpeg,txt,docx` — committed S0 default, superset of TBD-05), ≤ `max_upload_size_mb` (default 10) per file, ≤ `upload_max_files` (5) per request, stored name = server-generated UUID (never user input), DB stores metadata only, files land under `upload_dir` (gitignored).
- **Public Portal data discipline:** public track returns only public data — no internal notes, AI, assignment or audit (FR-PUB-06/07). Priority of a portal ticket = `MEDIUM` (design spec §8 note); status = `OPEN`; SLA deadlines computed from the active policy for that priority.
- **Writes are optimistic-locked:** every `PATCH`/status/assign body carries `version`; mismatch → 409 `VERSION_CONFLICT` (client reloads). Every business-field write appends `ticket_history` (old/new/actor/time) and an `audit_logs` row (PII-free).
- **S1 behavior must not regress:** `alembic check` empty; S1 auth/lockout/refresh + RBAC unchanged; existing unit (35) + integration (4) tests stay green.
- **UI:** Vietnamese labels, English identifiers; loading/empty/success/error states; double-submit disabled; dialogs for destructive status changes; access token stays in JS memory only. FE nav/guards mirror `deps._FEATURE_SCOPES`.
- Demo stack (db :5433 / backend :8001 / frontend :8080) stays up; the foreign `hethongticketai` stack + native postgres are never touched.

## Controller decisions recorded for reviewers (ratified, no human gate needed — resolve here not in the loop)

1. **Minimal assignment ships in S2** (user decision, AskUserQuestion): `POST /api/tickets/{id}/assign` for MANAGER/ADMIN sets `team_id` + optional `assigned_to` with basic validation (assignee ∈ team & active; Manager only into a team they manage), writes `ticket_history`(ASSIGNED) + audit. Full S3 (dialog UI polish, FR-ASG-01..10 extra, "needs re-assignment" flag) stays out.
2. **Unassigned ticket visibility:** ADMIN sees all; MANAGER sees tickets of teams they manage **plus tickets with `team_id IS NULL`**; AGENT sees tickets of any team they are an active member of **plus tickets `assigned_to = me`**. This makes the §10 S2 demo ("khách gửi → manager gán → agent thấy") runnable inside the slice.
3. **SLA pause is derived from `ticket_history`, no new column.** Transition to PENDING writes one `STATUS_CHANGED` row; on PENDING→IN_PROGRESS (only when the ticket's policy has `pause_on_pending`) the pause window = `now − last STATUS_CHANGED→PENDING.created_at`, and resolution/response deadlines are extended by that delta (design spec §9 wording: "deadline được bù thêm"), recorded as a `FIELD_UPDATED` history row. `pending_since()` (sla_service) reads the latest status event.
4. **Rate limiting = slowapi, scoped to /public only in S2** (`POST /api/public/tickets`, `POST /api/public/track`). `/auth/login` keeps its S1 account-lockout; extending to `/auth/login` + `/api/ai/*` rolls out where those are (S4/S7). `limiter.enabled = settings.rate_limit_enabled` so integration tests run with it off.
5. **Resolved/Closed timestamps** are written on transitions INTO those states and cleared on reopen out of them; `first_response_at` is stamped by the first PUBLIC comment (internal-only, S2) and never cleared.
6. **Internal ticket creation (`POST /api/tickets`) is out of S2** (§8.2 marks it "nếu được bật" and §10 S2 does not list it). Tickets enter via the Public Portal; staff-created tickets are deferred with S3.
7. **Assigning does not auto-change status** (UC-06 step 6 "nếu phù hợp"): the agent moves OPEN→IN_PROGRESS explicitly via the status endpoint. Assignment just sets responsibility (BR-07).
8. `GET /api/tickets/{id}` detail payload includes comments + attachments + history (the §8.2 standalone `GET comments`/`GET history` read endpoints are not separately implemented — no consumer needs them yet; UC-05 lists them as part of detail).

## File structure (map of what S2 creates/modifies)

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py            MODIFY: S2 Settings knobs
│   │   └── rate_limit.py        CREATE: slowapi limiter + init_rate_limit(app)
│   ├── api/
│   │   ├── public.py            CREATE: /api/public/tickets + /track
│   │   └── tickets.py           CREATE: /api/tickets (list/detail/update/status/assign/comments/attachments) + /api/attachments/{id}/download
│   ├── schemas/
│   │   ├── public.py            CREATE
│   │   └── ticket.py            CREATE
│   ├── services/
│   │   ├── state_machine.py     CREATE (pure)
│   │   ├── ticket_code.py       CREATE (pure + unique-code DB helper)
│   │   ├── file_rules.py        CREATE (pure)
│   │   ├── sla_service.py       CREATE (pure + 2 async DB helpers)
│   │   ├── storage.py           CREATE (save/remove/resolve uploads)
│   │   └── ticket_service.py    CREATE (scoping + create/update/status/assign + comment/attachment DB ops)
│   └── main.py                  MODIFY: mount public + tickets routers, call init_rate_limit
├── tests/
│   ├── unit/                    CREATE test_state_machine/test_sla/test_ticket_code/test_file_rules.py
│   └── integration/             CREATE test_ticket_service.py (Task 3) + test_http_tickets.py (Task 4)
├── pyproject.toml               MODIFY: + slowapi
frontend/
├── src/
│   ├── api/client.js            MODIFY: + postForm, + download
│   ├── lib/labels.js            CREATE: enum -> Vietnamese label/colour maps
│   ├── pages/
│   │   ├── PortalCreatePage.jsx CREATE
│   │   ├── PortalTrackPage.jsx  CREATE
│   │   ├── TicketsListPage.jsx  CREATE
│   │   └── TicketDetailPage.jsx CREATE
│   ├── styles/
│   │   ├── portal.css           CREATE
│   │   └── tickets.css          CREATE
│   └── App.jsx                  MODIFY: routes (/ portal, /track, /health, /app/tickets, /app/tickets/:id)
├── .gitignore                   MODIFY: + backend/uploads/
└── README.md                    MODIFY (Task 7): S2 demo block
```

## Key interfaces (consistency contract across tasks)

- `Settings` (config.py): existing + `upload_dir: str = "uploads"`, `upload_max_files: int = 5`, `sla_due_soon_minutes: int = 120`, `rate_limit_enabled: bool = True`, `public_create_rate: str = "20/hour"`, `public_track_rate: str = "60/hour"`.
- `AppError(status_code, error_code, message, details=None)` from `app.core.errors` — always raised with a §10.2 code (or the fixed 4xx transport codes above).
- `write_audit(session, *, action, entity_type, outcome, actor_id=None, entity_id=None, metadata=None, ip_address=None)` from `app.services.audit`.
- `get_session`, `get_current_user`, `require_roles(*roles)` from `app.db.session` / `app.core.deps` (S1, unchanged).
- Models import from their S0 modules: `app.models.ticket` → `Ticket, SlaPolicy, Comment, Attachment, TicketHistory`; `app.models.user` → `User`; `app.models.team` → `SupportTeam, TeamMember`; `app.models.enums` → `TicketStatus, TicketPriority, TicketCategory, Visibility, CommentSource, AuditOutcome, UserRole`.
- Pydantic outputs live in `app.schemas.ticket` / `app.schemas.public`; routers map ORM→schema with small module-level `to_*` helpers (S1 auth.py pattern).

---

### Task 1: Config knobs + slowapi dep + pure policy helpers (ticket code, state machine, file rules, SLA math)

**Files:**
- Modify: `backend/pyproject.toml` (add `slowapi` to `dependencies`)
- Modify: `backend/app/core/config.py` (S2 Settings knobs)
- Create: `backend/app/services/ticket_code.py`
- Create: `backend/app/services/state_machine.py`
- Create: `backend/app/services/file_rules.py`
- Create: `backend/app/services/sla_service.py`
- Create: `backend/tests/unit/test_ticket_code.py`
- Create: `backend/tests/unit/test_state_machine.py`
- Create: `backend/tests/unit/test_file_rules.py`
- Create: `backend/tests/unit/test_sla.py`

**Interfaces:**
- Consumes: S0 `Ticket`/`SlaPolicy` ORM (for the DB collision helper in `ticket_code.py`), `TicketStatus`/`TicketPriority` enums, `Settings` (`max_upload_size_mb`, `allowed_file_types` already exist).
- Produces (later tasks consume these exact signatures):
  - `Settings`: `upload_dir: str = "uploads"`, `upload_max_files: int = 5`, `sla_due_soon_minutes: int = 120`, `rate_limit_enabled: bool = True`, `public_create_rate: str = "20/hour"`, `public_track_rate: str = "60/hour"`.
  - `generate_ticket_code() -> str` (pure, `TK-` + 8 RFC 4648 base32 chars), `unique_ticket_code(session) -> str` (async DB retry loop).
  - `can_transition(current: str, target: str) -> bool`, `is_reopen(current: str, target: str) -> bool`, `STATUS_FLOW` dict.
  - `parse_allowed_extensions(allowed_csv: str) -> set[str]`, `extension_allowed(name: str, allowed: set[str]) -> bool`, `within_size(size_bytes: int, max_bytes: int) -> bool`.
  - `extend_deadline(due_at, pause_seconds) -> datetime`, `deadline_state(due_at, now, due_soon_minutes) -> str` (one of `overdue`/`due_soon`/`on_track`/`none`).

- [ ] **Step 1: Add the slowapi dependency + sync the host venv**

Edit `backend/pyproject.toml`: insert `"slowapi>=0.1.9",` after the `httpx>=0.27` line:

```toml
    "httpx>=0.27",
    "slowapi>=0.1.9",
```

Then sync the host venv (editable reinstall resolves the new dep):

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pip install -e ".[dev]" -q`
Expected: installs `slowapi` (and its `limits` dependency) with no errors. Confirm the installed `slowapi` Limiter exposes an `enabled` attribute (toggle for tests):
Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -c "from slowapi import Limiter; from slowapi.util import get_remote_address; import inspect; print('enabled' in inspect.signature(Limiter).parameters or hasattr(Limiter, 'enabled'))"`
Expected: prints `True`. (If `False`, note it in the task report — Task 4 falls back to huge test rate strings and the `RATE_LIMIT_ENABLED` env var alone.)

- [ ] **Step 2: Add the S2 Settings knobs**

Edit `backend/app/core/config.py` after the `allowed_file_types: str = "pdf,png,jpg,jpeg,txt,docx"` line (line 45):

```python
    upload_dir: str = "uploads"
    upload_max_files: int = 5

    # SLA (used from S2 onward: "due soon" badge threshold)
    sla_due_soon_minutes: int = 120

    # Rate limiting (S2: slowapi over /public only)
    rate_limit_enabled: bool = True
    public_create_rate: str = "20/hour"
    public_track_rate: str = "60/hour"
```

- [ ] **Step 3: Write the failing unit tests**

Create the four test files:

`backend/tests/unit/test_ticket_code.py`:
```python
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ticket_code


def test_generated_code_shape_and_alphabet():
    for _ in range(50):
        code = ticket_code.generate_ticket_code()
        assert re.fullmatch(r"TK-[A-Z2-7]{8}", code)  # RFC 4648 base32: A-Z + 2-7
```
(Note: no unique-code DB test here — `unique_ticket_code` is exercised in Task 3's integration tests.)

`backend/tests/unit/test_state_machine.py`:
```python
import pytest

from app.services.state_machine import STATUS_FLOW, can_transition, is_reopen


def test_open_can_go_to_in_progress_and_pending_only():
    assert can_transition("OPEN", "IN_PROGRESS")
    assert can_transition("OPEN", "PENDING")
    assert not can_transition("OPEN", "RESOLVED")
    assert not can_transition("OPEN", "CLOSED")


def test_in_progress_flow():
    assert can_transition("IN_PROGRESS", "PENDING")
    assert can_transition("IN_PROGRESS", "RESOLVED")
    assert not can_transition("IN_PROGRESS", "OPEN")


def test_pending_returns_to_in_progress():
    assert can_transition("PENDING", "IN_PROGRESS")
    assert not can_transition("PENDING", "RESOLVED")


def test_resolved_and_closed_reopen_to_in_progress():
    assert can_transition("RESOLVED", "CLOSED")
    assert can_transition("RESOLVED", "IN_PROGRESS")
    assert can_transition("CLOSED", "IN_PROGRESS")
    assert not can_transition("CLOSED", "OPEN")


def test_reopen_only_from_resolved_or_closed():
    assert is_reopen("RESOLVED", "IN_PROGRESS")
    assert is_reopen("CLOSED", "IN_PROGRESS")
    assert not is_reopen("OPEN", "IN_PROGRESS")
    assert not is_reopen("IN_PROGRESS", "PENDING")


def test_unknown_statuses_are_rejected():
    assert not can_transition("OPEN", "BOGUS")
    assert not can_transition("BOGUS", "IN_PROGRESS")
    assert STATUS_FLOW["OPEN"] == {"IN_PROGRESS", "PENDING"}
```

`backend/tests/unit/test_file_rules.py`:
```python
from app.services.file_rules import extension_allowed, parse_allowed_extensions, within_size


def test_parse_allowed_extensions_strips_and_lowercases():
    assert parse_allowed_extensions("PDF,png,JPG,jpeg,txt,docx") == {"pdf", "png", "jpg", "jpeg", "txt", "docx"}


def test_extension_allowed_case_insensitive():
    allowed = parse_allowed_extensions("pdf,png,jpg,jpeg,txt,docx")
    assert extension_allowed("report.PDF", allowed)
    assert extension_allowed("anh.JPG", allowed)
    assert not extension_allowed("virus.exe", allowed)
    assert not extension_allowed("noext", allowed)


def test_within_size_boundary():
    assert within_size(10 * 1024 * 1024, 10 * 1024 * 1024)  # exactly at the cap is allowed
    assert not within_size(10 * 1024 * 1024 + 1, 10 * 1024 * 1024)
    assert within_size(0, 10 * 1024 * 1024)
```

`backend/tests/unit/test_sla.py`:
```python
from datetime import datetime, timedelta, timezone

from app.services.sla_service import deadline_state, extend_deadline

_NOW = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)


def test_extend_deadline_shifts_by_pause():
    due = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert extend_deadline(due, 3600) == due + timedelta(hours=1)


def test_deadline_state_overdue_due_soon_on_track_none():
    assert deadline_state(_NOW - timedelta(minutes=1), _NOW, 120) == "overdue"
    assert deadline_state(_NOW + timedelta(minutes=30), _NOW, 120) == "due_soon"
    assert deadline_state(_NOW + timedelta(hours=5), _NOW, 120) == "on_track"
    assert deadline_state(None, _NOW, 120) == "none"
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_ticket_code.py tests/unit/test_state_machine.py tests/unit/test_file_rules.py tests/unit/test_sla.py -q`
Expected: FAIL with `ModuleNotFoundError: app.services.ticket_code` (or the missing modules).

- [ ] **Step 5: Implement the four helpers**

Create `backend/app/services/ticket_code.py`:
```python
"""Public-facing ticket codes: TK- + 8 RFC 4648 base32 chars (SRS 6.5, FR-PUB-03).

Base32 (A-Z, 2-7) excludes the look-alikes 0/O/1/I/L and is unambiguous when a
customer reads a code back over the phone. Codes are random, never sequential.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.ticket import Ticket

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"  # 32 chars: RFC 4648 base32

_PREFIX = "TK-"


def generate_ticket_code() -> str:
    return _PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))


async def unique_ticket_code(session: AsyncSession) -> str:
    """Return a fresh code guaranteed not to collide with an existing row.

    The tickets.ticket_code column is UNIQUE; a (vanishingly unlikely) collision
    must not surface as a 500 IntegrityError. Retry a few times, then fail loudly.
    """
    for _ in range(5):
        code = generate_ticket_code()
        exists = await session.execute(select(Ticket.id).where(Ticket.ticket_code == code))
        if exists.scalar_one_or_none() is None:
            return code
    raise AppError(500, "INTERNAL_ERROR", "Không thể tạo mã vé, vui lòng thử lại.")
```

Create `backend/app/services/state_machine.py`:
```python
"""Ticket status transition policy (SRS 3.2.2, FR-TIC-11). Pure and unit-tested."""

from app.models.enums import TicketStatus

# SRS 3.2.2: the ONLY legal transitions. A ticket never jumps to RESOLVED/CLOSED
# except from the state named; reopening always means -> IN_PROGRESS.
STATUS_FLOW: dict[str, set[str]] = {
    TicketStatus.OPEN.value: {TicketStatus.IN_PROGRESS.value, TicketStatus.PENDING.value},
    TicketStatus.IN_PROGRESS.value: {TicketStatus.PENDING.value, TicketStatus.RESOLVED.value},
    TicketStatus.PENDING.value: {TicketStatus.IN_PROGRESS.value},
    TicketStatus.RESOLVED.value: {TicketStatus.IN_PROGRESS.value, TicketStatus.CLOSED.value},
    TicketStatus.CLOSED.value: {TicketStatus.IN_PROGRESS.value},
}


def can_transition(current: str, target: str) -> bool:
    return target in STATUS_FLOW.get(current, set())


def is_reopen(current: str, target: str) -> bool:
    """Reopen = moving a RESOLVED or CLOSED ticket back to IN_PROGRESS (FR-TIC-11)."""
    return current in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value) and target == TicketStatus.IN_PROGRESS.value
```

Create `backend/app/services/file_rules.py`:
```python
"""Upload allowlist + size rules (SRS TBD-05/FR-PUB, SRS 10.1; design spec 8)."""

from pathlib import PurePosixPath


def parse_allowed_extensions(allowed_csv: str) -> set[str]:
    """'pdf,png,jpg,jpeg,txt,docx' -> {'pdf','png',...} (lowercased, trimmed)."""
    return {ext.strip().lower() for ext in allowed_csv.split(",") if ext.strip()}


def extension_allowed(filename: str, allowed: set[str]) -> bool:
    ext = PurePosixPath(filename).suffix.lower().lstrip(".")
    return ext in allowed and ext != ""


def within_size(size_bytes: int, max_bytes: int) -> bool:
    return size_bytes <= max_bytes
```

Create `backend/app/services/sla_service.py`:
```python
"""SLA deadline math. Pure helpers (unit-tested) live here; async DB helpers used
by the ticket service are added in Task 3. Pause-on-pending is derived from
ticket_history (Controller decision 3): no column on tickets, no migration.
"""

from datetime import datetime, timedelta


def extend_deadline(due_at: datetime, pause_seconds: float) -> datetime:
    """Shift a deadline by the pause window (SRS FR-SLA: 'deadline được bù thêm')."""
    return due_at + timedelta(seconds=pause_seconds)


def deadline_state(due_at: datetime | None, now: datetime, due_soon_minutes: int) -> str:
    """Classify a deadline for the UI: overdue | due_soon | on_track | none."""
    if due_at is None:
        return "none"
    if due_at <= now:
        return "overdue"
    if due_at <= now + timedelta(minutes=due_soon_minutes):
        return "due_soon"
    return "on_track"
```

- [ ] **Step 6: Run the unit tests to verify they pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_ticket_code.py tests/unit/test_state_machine.py tests/unit/test_file_rules.py tests/unit/test_sla.py -q`
Expected: all pass (6 + 6 + 3 + 4 = 19 new tests).

- [ ] **Step 7: Run the whole unit suite (no regressions)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: all pass (S1's 35 unit tests still green + the 19 new = 54 total).

- [ ] **Step 8: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/pyproject.toml backend/app/core/config.py backend/app/services/ticket_code.py backend/app/services/state_machine.py backend/app/services/file_rules.py backend/app/services/sla_service.py backend/tests/unit/test_ticket_code.py backend/tests/unit/test_state_machine.py backend/tests/unit/test_file_rules.py backend/tests/unit/test_sla.py
git commit -m "feat(backend): S2 config knobs + pure ticket/state/file/SLA policy helpers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Pydantic schemas + file storage service + rate-limit module

**Files:**
- Create: `backend/app/schemas/public.py`
- Create: `backend/app/schemas/ticket.py`
- Create: `backend/app/services/storage.py`
- Create: `backend/app/core/rate_limit.py`
- Create: `backend/tests/unit/test_storage.py`
- Create: `backend/tests/unit/test_rate_limit.py`

**Interfaces:**
- Consumes: Task 1 `Settings`, `parse_allowed_extensions`/`extension_allowed`/`within_size`; `AppError`; S0 enums/`get_remote_address` from slowapi.
- Produces (later tasks consume these exact names):
  - `schemas.public`: `PortalCreateRequest` (`requester_name`, `requester_email`, `subject`, `description`, `category|None`), `PortalTicketOut`, `PortalTrackRequest` (`email`, `ticket_code`), `PortalTrackResponse` (with `comments: list[PortalCommentOut]`), `PortalCommentOut`.
  - `schemas.ticket`: `TicketListItem`, `TicketListResponse`, `CommentOut`, `AttachmentOut`, `HistoryOut`, `TeamMemberOut`, `TeamOut`, `TicketDetail`, `TicketUpdateRequest`, `StatusUpdateRequest`, `AssignRequest`.
  - `storage.store_upload(upload, *, upload_dir: Path, allowed: set[str], max_bytes: int) -> StoredFile`, `storage.resolve_upload(storage_path: str) -> Path`, `storage.remove_stored(storage_path: str) -> None`.
  - `rate_limit.limiter`, `rate_limit.init_rate_limit(app)`.
  - Update `backend/app/core/config.py` is untouched this task (Task 1 added its knobs).

- [ ] **Step 1: Write the failing storage + rate-limit tests**

Create `backend/tests/unit/test_storage.py`:
```python
from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app.core.errors import AppError
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import resolve_upload, store_upload

ALLOWED = parse_allowed_extensions("pdf,png,jpg,jpeg,txt,docx")


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(BytesIO(content), filename=name)


async def test_store_upload_writes_file_and_returns_metadata(tmp_path):
    stored = await store_upload(_upload("bao-cao.pdf", b"%PDF-1.4 hello"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=100)
    assert stored.original_name == "bao-cao.pdf"
    assert stored.size_bytes == 12
    assert stored.stored_name.endswith(".pdf")
    # server-generated name, never the user's filename
    assert stored.stored_name != "bao-cao.pdf"
    assert stored.storage_path.endswith(stored.stored_name)
    path = resolve_upload(stored.storage_path)
    assert path.read_bytes() == b"%PDF-1.4 hello"


async def test_store_upload_rejects_disallowed_type_and_writes_nothing(tmp_path):
    with pytest.raises(AppError) as exc:
        await store_upload(_upload("virus.exe", b"MZ"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=100)
    assert exc.value.status_code == 415
    assert exc.value.error_code == "FILE_TYPE_NOT_ALLOWED"
    assert list(tmp_path.iterdir()) == []


async def test_store_upload_rejects_oversized_and_removes_partial_file(tmp_path):
    with pytest.raises(AppError) as exc:
        await store_upload(_upload("big.txt", b"1234567890"), upload_dir=tmp_path, allowed=ALLOWED, max_bytes=4)
    assert exc.value.status_code == 413
    assert exc.value.error_code == "FILE_TOO_LARGE"
    assert list(tmp_path.iterdir()) == []
```

Create `backend/tests/unit/test_rate_limit.py`:
```python
import json

import pytest
from slowapi.errors import RateLimitExceeded

from app.core.rate_limit import _rate_limit_exceeded_handler


async def test_rate_limit_handler_returns_uniform_429_body():
    resp = await _rate_limit_exceeded_handler(None, RateLimitExceeded())
    assert resp.status_code == 429
    body = json.loads(resp.body)
    assert body == {"error_code": "RATE_LIMITED", "message": body["message"], "details": None}
    assert body["error_code"] == "RATE_LIMITED"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_storage.py tests/unit/test_rate_limit.py -q`
Expected: FAIL with `ModuleNotFoundError: app.schemas` / `app.services.storage` / `app.core.rate_limit` (as the modules do not exist yet).

- [ ] **Step 3: Create the public + staff schemas**

Create `backend/app/schemas/public.py`:
```python
"""Public Portal request/response schemas. Only public, PII-the-customer-owns data
leaves this boundary (SRS FR-PUB-06/07); never internal notes, AI or assignment.
"""

from datetime import datetime

from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_CATEGORY_PATTERN = r"^(TECHNICAL|ACCOUNT|BILLING|GENERAL|OTHER)$"


class PortalCreateRequest(BaseModel):
    requester_name: str = Field(..., min_length=2, max_length=100)
    requester_email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN)
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=20000)
    category: str | None = Field(default=None, pattern=_CATEGORY_PATTERN)  # optional; NULL otherwise


class PortalTicketOut(BaseModel):
    ticket_code: str
    status: str
    subject: str
    created_at: datetime


class PortalCommentOut(BaseModel):
    id: str
    content: str
    created_at: datetime


class PortalTrackRequest(BaseModel):
    email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN)
    ticket_code: str = Field(..., min_length=3, max_length=30)


class PortalTrackResponse(BaseModel):
    ticket_code: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    comments: list[PortalCommentOut]
```

Create `backend/app/schemas/ticket.py`:
```python
"""Staff ticket schemas (SRS 8.2, 10.1). 'version' is the optimistic-lock guard:
a write body must echo the version it read, else the service returns 409
VERSION_CONFLICT (SRS 10.2)."""

from datetime import datetime

from pydantic import BaseModel, Field


class TicketListItem(BaseModel):
    id: str
    ticket_code: str
    subject: str
    category: str | None
    priority: str
    status: str
    requester_name: str
    requester_email: str
    team_id: str | None
    assigned_to: str | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class TicketListResponse(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class CommentOut(BaseModel):
    id: str
    author_id: str | None
    author_name: str | None  # staff full name; None => customer-authored
    content: str
    visibility: str  # PUBLIC | INTERNAL
    source: str      # HUMAN | AI_ASSISTED
    created_at: datetime
    edited_at: datetime | None


class AttachmentOut(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    uploaded_by: str | None


class HistoryOut(BaseModel):
    id: str
    event_type: str  # STATUS_CHANGED | ASSIGNED | FIELD_UPDATED
    field_name: str | None
    old_value: dict | str | None
    new_value: dict | str | None
    changed_by: str | None
    reason: str | None
    created_at: datetime


class TeamMemberOut(BaseModel):
    id: str
    full_name: str
    team_role: str  # MANAGER | MEMBER


class TeamOut(BaseModel):
    id: str
    name: str
    members: list[TeamMemberOut]


class TicketDetail(BaseModel):
    id: str
    ticket_code: str
    requester_name: str
    requester_email: str
    subject: str
    description: str
    category: str | None
    priority: str
    status: str
    team_id: str | None
    assigned_to: str | None
    sla_policy_id: str | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    comments: list[CommentOut]
    attachments: list[AttachmentOut]
    history: list[HistoryOut]


class TicketUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=20000)
    category: str | None = Field(default=None, pattern=r"^(TECHNICAL|ACCOUNT|BILLING|GENERAL|OTHER)$")
    priority: str | None = Field(default=None, pattern=r"^(LOW|MEDIUM|HIGH|URGENT)$")
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(OPEN|IN_PROGRESS|PENDING|RESOLVED|CLOSED)$")
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)


class AssignRequest(BaseModel):
    team_id: str = Field(..., min_length=1)
    assigned_to: str | None = None
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)
```

- [ ] **Step 4: Implement the storage service**

Create `backend/app/services/storage.py`:
```python
"""Server-side storage for ticket attachments (SRS file rules; design spec 8).

Only validated bytes reach disk. A file is streamed in chunks, counted against
max_bytes, stored under a server-generated UUID name (never the user's filename),
and returned as a StoredFile carrying the metadata the Attachment row needs. The
router/service owns the DB row; this module owns the bytes.
"""

import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.errors import AppError
from app.services.file_rules import extension_allowed, within_size

_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    stored_name: str
    storage_path: str  # forward-slash path (portable host <-> container bind mount)
    original_name: str
    mime_type: str
    size_bytes: int


def _mime_for(filename: str, declared: str | None) -> str:
    if declared and "/" in declared:
        return declared
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


async def store_upload(
    upload: UploadFile, *, upload_dir: Path, allowed: set[str], max_bytes: int
) -> StoredFile:
    """Validate + stream one upload to disk under a fresh UUID name.

    Raises 415 FILE_TYPE_NOT_ALLOWED or 413 FILE_TOO_LARGE (SRS 10.2 codes).
    """
    original = upload.filename or "file"
    if not extension_allowed(original, allowed):
        raise AppError(415, "FILE_TYPE_NOT_ALLOWED", "Loại tệp không được phép tải lên.")
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = PurePosixPath(original).suffix.lower()
    stored_name = uuid.uuid4().hex + ext
    # Forward-slash storage_path so a row written in the host venv resolves the
    # same under the Linux container's bind mount of ./backend.
    storage_path = (PurePosixPath(upload_dir.as_posix()) / stored_name).as_posix()
    target = Path(storage_path)
    size = 0
    try:
        with target.open("wb") as fh:
            while chunk := await upload.read(_CHUNK):
                size += len(chunk)
                if not within_size(size, max_bytes):
                    raise AppError(413, "FILE_TOO_LARGE", "Tệp vượt quá kích thước tối đa cho phép.")
                fh.write(chunk)
    except AppError:
        target.unlink(missing_ok=True)
        raise
    return StoredFile(
        stored_name=stored_name,
        storage_path=storage_path,
        original_name=original,
        mime_type=_mime_for(original, upload.content_type),
        size_bytes=size,
    )


def resolve_upload(storage_path: str) -> Path:
    p = Path(storage_path)
    return p if p.is_absolute() else Path.cwd() / p


def remove_stored(storage_path: str) -> None:
    resolve_upload(storage_path).unlink(missing_ok=True)
```

- [ ] **Step 5: Implement the rate-limit module**

Create `backend/app/core/rate_limit.py`:
```python
"""slowapi limiter for the /public endpoints (design spec 3; SRS 8.3 429).

Only /public/* is rate-limited in S2 (Controller decision 4). The limiter's
`enabled` flag is bound to Settings.rate_limit_enabled at app init, so the
integration suite runs with RATE_LIMIT_ENABLED=false. The 429 body keeps the
uniform {error_code, message, details} envelope (error_code RATE_LIMITED).
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address)


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "RATE_LIMITED",
            "message": "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn, vui lòng thử lại sau.",
            "details": None,
        },
    )


def init_rate_limit(app: FastAPI) -> None:
    settings = get_settings()
    limiter.enabled = settings.rate_limit_enabled
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_storage.py tests/unit/test_rate_limit.py -q`
Expected: all pass (3 storage + 1 rate-limit). If the installed Starlette `UploadFile` constructor signature differs (`filename` positional), adapt the `_upload` helper in the test to the installed signature — the behaviour asserted is unchanged.

- [ ] **Step 7: Run the whole unit suite (no regressions)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: all pass (58 total now).

- [ ] **Step 8: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/schemas/public.py backend/app/schemas/ticket.py backend/app/services/storage.py backend/app/core/rate_limit.py backend/tests/unit/test_storage.py backend/tests/unit/test_rate_limit.py
git commit -m "feat(backend): S2 pydantic schemas, file storage service, rate-limit module

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Ticket service — scoping, create/update/status/assign/comments/attachments, history + audit

**Why one task:** the ticket service is one cohesive transaction boundary (design spec §5.1: service owns business logic + history + audit). Every write helper shares the same version/scope/history conventions, so splitting them would force a reviewer to approve half a convention.

**Files:**
- Create: `backend/app/services/ticket_service.py`
- Create: `backend/tests/integration/test_ticket_service.py`

**Interfaces:**
- Consumes: Task 1 helpers (`can_transition`/`is_reopen`/`unique_ticket_code`), Task 2 schemas' field conventions + `StoredFile`, S0 models/enums, `write_audit` (S1).
- Produces (Task 4 routers consume these exact names):
  - `member_team_ids(session, *, user_id, manager_only=False) -> list[UUID]`
  - `get_scoped_ticket(session, *, user, ticket_id) -> Ticket` (raises 404 `TICKET_NOT_FOUND` for unknown **or** out-of-scope)
  - `list_tickets(session, *, user, page, page_size, status=None, q=None, assigned_to_me=False) -> tuple[int, list[dict]]`
  - `create_portal_ticket(session, *, requester_name, requester_email, subject, description, category, files) -> Ticket`
  - `update_ticket(session, *, ticket, actor, changes, reason, expected_version) -> Ticket`
  - `change_status(session, *, ticket, actor, target, reason, expected_version) -> Ticket`
  - `assign_ticket(session, *, ticket, actor, team_id, assigned_to, reason, expected_version) -> Ticket`
  - `add_comment(session, *, ticket, actor, content, visibility, files) -> Comment`
  - `add_attachments(session, *, ticket, actor, files) -> list[Attachment]`
  - `teams_with_members(session, *, user) -> list[tuple[SupportTeam, list[TeamMember]]]`
  - `track_public(session, *, email, ticket_code) -> Ticket`

- [ ] **Step 1: Write the failing integration tests**

Create `backend/tests/integration/test_ticket_service.py`. It runs against the real compose DB (:5433) like S1's `test_auth.py`, and every test builds **its own throwaway org** (users/teams/tickets created by the test and removed afterwards) so the seeded demo data is never touched:

```python
"""Integration: ticket service flows against the real DB (S2 design spec 10: Test).

Run with the compose DB up and:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support

Every test creates its own throwaway org (users + team + ticket) and removes it
afterwards, so the seeded demo accounts/tickets are never modified.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.enums import TeamRole, TicketStatus, UserRole
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services import ticket_service

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)

_NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


def _tag() -> str:
    return uuid.uuid4().hex[:12]


async def _add_user(email, full_name, role) -> User:
    async with AsyncSessionLocal() as s:
        u = User(full_name=full_name, email=email, password_hash=hash_password("It@123456"), role=role, is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _add_team(name) -> SupportTeam:
    async with AsyncSessionLocal() as s:
        t = SupportTeam(name=name, description="s2 test")
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


async def _add_membership(team_id, user_id, team_role: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(TeamMember(team_id=team_id, user_id=user_id, team_role=team_role, is_active=True))
        await s.commit()


async def _create_org():
    """Return (admin, manager_a, agent_a, agent_b, team_a, team_b). agent_a is in
    team_a (managed by manager_a); agent_b is in team_b (NOT managed by manager_a)."""
    tag = _tag()
    admin = await _add_user(f"admin.{tag}@example.com", "Admin S2", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý S2", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B", UserRole.AGENT.value)
    team_a = await _add_team(f"Team A {tag}")
    team_b = await _add_team(f"Team B {tag}")
    await _add_membership(team_a.id, manager.id, TeamRole.MANAGER.value)
    await _add_membership(team_a.id, agent_a.id, TeamRole.MEMBER.value)
    await _add_membership(team_b.id, agent_b.id, TeamRole.MEMBER.value)
    return {"admin": admin, "manager": manager, "agent_a": agent_a, "agent_b": agent_b,
            "team_a": team_a, "team_b": team_b, "user_ids": [admin.id, manager.id, agent_a.id, agent_b.id]}


async def _create_portal_ticket():
    tag = _tag()
    async with AsyncSessionLocal() as s:
        ticket = await ticket_service.create_portal_ticket(
            s, requester_name="Khách S2", requester_email=f"khach.{tag}@example.com",
            subject="Không truy cập được hệ thống", description="Tôi không đăng nhập được từ sáng nay.",
            category=None, files=None,
        )
        return ticket


async def _remove_ticket(ticket_id) -> None:
    """Delete one org-created ticket + its audit rows (AuditLog has no CASCADE)."""
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.entity_id == ticket_id))
        await s.execute(delete(Ticket).where(Ticket.id == ticket_id))
        await s.commit()


async def _cleanup_org(org, ticket_ids: list) -> None:
    """Remove everything ONE test created — and ONLY that. Precision is what keeps
    the seeded TK-DEMO tickets (all `*.customer@example.com`, on the seeded teams)
    safe on the shared :5433 DB: never delete by requester-email LIKE, never delete
    audit rows by entity_type alone. Order matters: audit rows have no ON DELETE
    CASCADE, so clear them before their users/teams go."""
    user_ids = org["user_ids"]
    team_ids = [org["team_a"].id, org["team_b"].id]
    ids = list(ticket_ids)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        if ids:
            await s.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
            # Cascades comments/history/attachments/ai_results rows.
            await s.execute(delete(Ticket).where(Ticket.id.in_(ids)))
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


async def test_create_portal_ticket_sets_defaults_and_deadlines():
    ticket = await _create_portal_ticket()
    try:
        assert ticket.status == TicketStatus.OPEN.value
        assert ticket.priority == "MEDIUM"
        assert ticket.team_id is None and ticket.assigned_to is None
        assert ticket.requester_email == ticket.requester_email.lower()
        assert ticket.resolution_due_at is not None  # seeded MEDIUM SLA policy applied
        assert ticket.first_response_due_at is not None
        assert ticket.version == 1
    finally:
        await _remove_ticket(ticket.id)


async def test_scoping_admin_all_manager_sees_unassigned_agent_denied():
    org = await _create_org()
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            # ADMIN: any ticket.
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.id == ticket.id
            # MANAGER: the unassigned portal ticket is visible (Controller decision 2).
            t2 = await ticket_service.get_scoped_ticket(s, user=org["manager"], ticket_id=ticket.id)
            assert t2.id == ticket.id
            # AGENT of team B (ticket has no team, not assigned): out of scope -> 404.
            with pytest.raises(AppError) as exc:
                await ticket_service.get_scoped_ticket(s, user=org["agent_b"], ticket_id=ticket.id)
            assert exc.value.status_code == 404 and exc.value.error_code == "TICKET_NOT_FOUND"
            # Unknown id is the same 404 (anti-leak).
            with pytest.raises(AppError) as exc2:
                await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=uuid.uuid4())
            assert exc2.value.status_code == 404 and exc2.value.error_code == "TICKET_NOT_FOUND"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_assign_manager_lite_and_agent_then_sees_ticket():
    org = await _create_org()
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["manager"], ticket_id=ticket.id)
            t = await ticket_service.assign_ticket(
                s, ticket=t, actor=org["manager"], team_id=org["team_a"].id,
                assigned_to=org["agent_a"].id, reason="Gán cho team A", expected_version=t.version,
            )
            assert t.team_id == org["team_a"].id and t.assigned_to == org["agent_a"].id
            assert t.version == 2
        # agent_a (member of team A / now assigned) can see it; agent_b cannot.
        async with AsyncSessionLocal() as s:
            t2 = await ticket_service.get_scoped_ticket(s, user=org["agent_a"], ticket_id=ticket.id)
            assert t2.id == ticket.id
            with pytest.raises(AppError):
                await ticket_service.get_scoped_ticket(s, user=org["agent_b"], ticket_id=ticket.id)
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_assign_validation_manager_cross_team_and_bad_assignee():
    org = await _create_org()
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["manager"], ticket_id=ticket.id)
            # Manager cannot assign into a team they don't manage -> 403 ACCESS_DENIED.
            with pytest.raises(AppError) as exc:
                await ticket_service.assign_ticket(
                    s, ticket=t, actor=org["manager"], team_id=org["team_b"].id,
                    assigned_to=None, reason=None, expected_version=t.version,
                )
            assert exc.value.status_code == 403 and exc.value.error_code == "ACCESS_DENIED"
            # ADMIN can, but assignee must be an active member of that team.
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            with pytest.raises(AppError) as exc2:
                await ticket_service.assign_ticket(
                    s, ticket=t, actor=org["admin"], team_id=org["team_a"].id,
                    assigned_to=org["agent_b"].id, reason=None, expected_version=t.version,
                )
            assert exc2.value.error_code == "ASSIGNEE_NOT_IN_TEAM"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_status_flow_version_conflict_and_reopen_requires_reason():
    org = await _create_org()
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            # The unassigned portal ticket is out of agent_a's scope; admin sees it.
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            # OPEN -> IN_PROGRESS -> RESOLVED
            t = await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="IN_PROGRESS", reason=None, expected_version=t.version)
            assert t.status == "IN_PROGRESS"
            t = await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="RESOLVED", reason=None, expected_version=t.version)
            assert t.resolved_at is not None
            # Reopen without a reason is refused (FR-TIC-11).
            with pytest.raises(AppError) as exc:
                await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="IN_PROGRESS", reason=None, expected_version=t.version)
            assert exc.value.error_code == "INVALID_STATUS_TRANSITION"
            # Reopen with a reason clears resolved_at.
            t = await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="IN_PROGRESS", reason="Khách phản hồi lại", expected_version=t.version)
            assert t.status == "IN_PROGRESS" and t.resolved_at is None
            # Stale version -> 409.
            with pytest.raises(AppError) as exc2:
                await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="PENDING", reason=None, expected_version=1)
            assert exc2.value.status_code == 409 and exc2.value.error_code == "VERSION_CONFLICT"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_sla_pause_on_pending_extends_deadlines():
    org = await _create_org()
    async with AsyncSessionLocal() as s:
        policy = SlaPolicy(name="pause test", priority="LOW", first_response_minutes=60,
                           resolution_minutes=120, pause_on_pending=True,
                           effective_from=_NOW - timedelta(days=1), is_active=True)
        s.add(policy)
        await s.flush()
        tag = _tag()
        t = Ticket(ticket_code=f"TK-{tag}", requester_name="Khách", requester_email=f"p.{tag}@example.com",
                   subject="Test pause", description="Nội dung đủ dài cho ticket test pause.",
                   priority="LOW", status="PENDING", version=1,
                   sla_policy_id=policy.id,
                   first_response_due_at=_NOW + timedelta(hours=2),
                   resolution_due_at=_NOW + timedelta(hours=4))
        s.add(t)
        await s.flush()
        # Simulate the earlier transition into PENDING 30 minutes ago.
        s.add(TicketHistory(ticket_id=t.id, changed_by=None, event_type="STATUS_CHANGED",
                            field_name="status", old_value="IN_PROGRESS", new_value="PENDING",
                            reason=None, created_at=_NOW - timedelta(minutes=30)))
        await s.commit()
        ticket_id = t.id
        policy_id = policy.id
        old_due = t.resolution_due_at
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket_id)
            t = await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="IN_PROGRESS", reason=None, expected_version=t.version)
            assert t.resolution_due_at >= old_due + timedelta(minutes=29)  # ~30 min added back
    finally:
        await _cleanup_org(org, [ticket_id])  # also removes the history + audit rows
        async with AsyncSessionLocal() as s:
            await s.execute(delete(SlaPolicy).where(SlaPolicy.id == policy_id))
            await s.commit()


async def test_public_comment_first_response_and_internal_hidden_from_track():
    org = await _create_org()
    ticket = await _create_portal_ticket()
    email = ticket.requester_email
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            # PUBLIC staff comment stamps first_response_at.
            t = await ticket_service.change_status(s, ticket=t, actor=org["admin"], target="IN_PROGRESS", reason=None, expected_version=t.version)
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"], content="Chúng tôi đang kiểm tra, vui lòng chờ.", visibility="PUBLIC", files=None)
            assert t.first_response_at is not None
            # INTERNAL note is invisible to the customer.
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"], content="Nghi do ISP ben khach hang.", visibility="INTERNAL", files=None)
            await s.commit()
        async with AsyncSessionLocal() as s:
            tracked = await ticket_service.track_public(s, email=email, ticket_code=ticket.ticket_code)
            pub = [c for c in tracked.comments if c.deleted_at is None]
            assert all(c.visibility == "PUBLIC" for c in pub)
            assert len(pub) == 1
        async with AsyncSessionLocal() as s:
            with pytest.raises(AppError) as exc:
                await ticket_service.track_public(s, email="wrong@example.com", ticket_code=ticket.ticket_code)
            assert exc.value.status_code == 404 and exc.value.error_code == "TICKET_NOT_FOUND"
    finally:
        await _cleanup_org(org, [ticket.id])
```

> Note for the implementer: every delete in the helpers above is scoped to ids the test itself created (`ticket_ids`/`user_ids`/team ids). Never broaden them to requester-email LIKE or `entity_type` alone — the shared :5433 DB also holds the seeded `TK-DEMO*` tickets (all `*.customer@example.com`, on the seeded teams) and audit rows written by other tests; a broad delete would destroy demo data.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" .venv/Scripts/python -m pytest tests/integration/test_ticket_service.py -q`
Expected: FAIL with `ModuleNotFoundError: app.services.ticket_service` (compose DB must be up on :5433).

- [ ] **Step 3: Implement the ticket service**

Create `backend/app/services/ticket_service.py`:

```python
"""Ticket domain service: scoping + create/update/status/assign + comments/attachments.

Design spec 5.1: the service owns business rules, optimistic locking, history and
audit rows; routers parse HTTP and call here. Scope checks use Controller decision
2: ADMIN=all, MANAGER=managed teams + unassigned (team_id IS NULL) + assigned to me,
AGENT=member teams + assigned to me. An out-of-scope OR unknown ticket is the SAME
404 TICKET_NOT_FOUND (anti-leak, SRS AC-SEC). A write body must echo `version`
(optimistic lock, SRS VERSION_CONFLICT -> 409). Pause-on-pending is derived from
ticket_history (decision 3): no column, no migration.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.audit import AuditOutcome
from app.models.enums import CommentSource, TicketStatus, UserRole
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import Attachment, Comment, SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services.audit import write_audit
from app.services.sla_service import extend_deadline
from app.services.state_machine import can_transition, is_reopen
from app.services.storage import StoredFile
from app.services.ticket_code import unique_ticket_code

ENTITY_TICKET = "ticket"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm_email(email: str) -> str:
    return email.strip().lower()


# ---- scoping helpers ----------------------------------------------------------


async def member_team_ids(session: AsyncSession, *, user_id, manager_only: bool = False) -> list[uuid.UUID]:
    stmt = select(TeamMember.team_id).where(
        TeamMember.user_id == user_id, TeamMember.is_active.is_(True)
    )
    if manager_only:
        stmt = stmt.where(TeamMember.team_role == "MANAGER")
    return list((await session.execute(stmt)).scalars())


async def _view_team_ids(session: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """None => everything (ADMIN). MANAGER -> managed teams; AGENT -> member teams."""
    if user.role == UserRole.ADMIN.value:
        return None
    return await member_team_ids(session, user_id=user.id, manager_only=(user.role == UserRole.MANAGER.value))


def _can_view(user: User, ticket: Ticket, view_ids: list[uuid.UUID] | None) -> bool:
    if user.role == UserRole.ADMIN.value:
        return True
    if ticket.assigned_to == user.id:
        return True
    if ticket.team_id is not None and view_ids and ticket.team_id in view_ids:
        return True
    if user.role == UserRole.MANAGER.value and ticket.team_id is None:
        return True  # unassigned pool is a manager's job (Controller decision 2)
    return False


def _scope_conds(user: User, view_ids: list[uuid.UUID] | None):
    if user.role == UserRole.ADMIN.value:
        return []
    conds = [Ticket.assigned_to == user.id]
    if view_ids:
        conds.append(Ticket.team_id.in_(view_ids))
    if user.role == UserRole.MANAGER.value:
        conds.append(Ticket.team_id.is_(None))
    return [or_(*conds)]


async def get_scoped_ticket(session: AsyncSession, *, user: User, ticket_id) -> Ticket:
    """Fetch one ticket the user may view; unknown OR out-of-scope -> 404 (anti-leak)."""
    try:
        tid = uuid.UUID(str(ticket_id))
    except ValueError:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy vé hỗ trợ.")
    ticket = await session.get(Ticket, tid)
    if ticket is None or not _can_view(user, ticket, await _view_team_ids(session, user)):
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy vé hỗ trợ.")
    return ticket


# ---- history / audit / version helpers ----------------------------------------


def _add_history(session: AsyncSession, *, ticket_id, changed_by, event_type: str,
                 field_name: str | None = None, old_value=None, new_value=None, reason: str | None = None) -> None:
    session.add(TicketHistory(ticket_id=ticket_id, changed_by=changed_by, event_type=event_type,
                              field_name=field_name, old_value=old_value, new_value=new_value, reason=reason))


def _ensure_version(ticket: Ticket, expected: int) -> None:
    if ticket.version != expected:
        raise AppError(409, "VERSION_CONFLICT", "Dữ liệu đã được cập nhật ở nơi khác. Vui lòng tải lại trang và thử lại.")


def _pending_since(ticket: Ticket) -> datetime | None:
    """Latest STATUS_CHANGED -> PENDING timestamp on this (already loaded) ticket."""
    pending_times = [
        h.created_at for h in ticket.history
        if h.event_type == "STATUS_CHANGED" and h.new_value == TicketStatus.PENDING.value
    ]
    return max(pending_times) if pending_times else None


# ---- list / read --------------------------------------------------------------


_ITEM_COLS = (
    Ticket.id, Ticket.ticket_code, Ticket.subject, Ticket.category, Ticket.priority,
    Ticket.status, Ticket.requester_name, Ticket.requester_email, Ticket.team_id,
    Ticket.assigned_to, Ticket.first_response_due_at, Ticket.resolution_due_at,
    Ticket.created_at, Ticket.updated_at, Ticket.version,
)


def _row_to_item(row) -> dict:
    return {
        "id": str(row["id"]), "ticket_code": row["ticket_code"], "subject": row["subject"],
        "category": row["category"], "priority": row["priority"], "status": row["status"],
        "requester_name": row["requester_name"], "requester_email": row["requester_email"],
        "team_id": str(row["team_id"]) if row["team_id"] else None,
        "assigned_to": str(row["assigned_to"]) if row["assigned_to"] else None,
        "first_response_due_at": row["first_response_due_at"], "resolution_due_at": row["resolution_due_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"], "version": row["version"],
    }


async def list_tickets(session: AsyncSession, *, user: User, page: int, page_size: int,
                       status: str | None = None, q: str | None = None, assigned_to_me: bool = False):
    view_ids = await _view_team_ids(session, user)
    conds = _scope_conds(user, view_ids)
    if status:
        conds.append(Ticket.status == status)
    if q:
        needle = f"%{q.strip().lower()}%"
        conds.append(or_(
            func.lower(Ticket.ticket_code).like(needle),
            func.lower(Ticket.subject).like(needle),
            func.lower(Ticket.requester_name).like(needle),
            func.lower(Ticket.requester_email).like(needle),
        ))
    if assigned_to_me:
        conds.append(Ticket.assigned_to == user.id)
    total = int((await session.execute(select(func.count(Ticket.id)).where(*conds))).scalar_one())
    stmt = (
        select(*_ITEM_COLS)
        .where(*conds)
        .order_by(Ticket.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return total, [_row_to_item(r) for r in rows]


async def teams_with_members(session: AsyncSession, *, user: User):
    """Team + active-members pickers for the assign dialog (Controller decision 1).

    MANAGER sees only the teams they manage; ADMIN sees all teams.
    """
    if user.role == UserRole.MANAGER.value:
        ids = await member_team_ids(session, user_id=user.id, manager_only=True)
        team_stmt = select(SupportTeam).where(SupportTeam.id.in_(ids), SupportTeam.is_active.is_(True))
    else:  # ADMIN
        team_stmt = select(SupportTeam).where(SupportTeam.is_active.is_(True))
    teams = (await session.execute(team_stmt.order_by(SupportTeam.name))).scalars().all()
    result = []
    for team in teams:
        members = (
            await session.execute(
                select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))
                .order_by(TeamMember.team_role, TeamMember.joined_at)
            )
        ).scalars().all()
        result.append((team, members))
    return result


# ---- create (public portal) ---------------------------------------------------


async def _active_sla_for_priority(session: AsyncSession, priority: str, now: datetime) -> SlaPolicy | None:
    stmt = (
        select(SlaPolicy)
        .where(
            SlaPolicy.priority == priority,
            SlaPolicy.is_active.is_(True),
            SlaPolicy.effective_from <= now,
            or_(SlaPolicy.effective_to.is_(None), SlaPolicy.effective_to > now),
        )
        .order_by(SlaPolicy.effective_from.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _add_attachment_rows(session: AsyncSession, *, ticket_id, files: list[StoredFile],
                         comment_id=None, uploaded_by=None) -> None:
    for f in files:
        session.add(Attachment(
            ticket_id=ticket_id, comment_id=comment_id, original_name=f.original_name,
            stored_name=f.stored_name, storage_path=f.storage_path, mime_type=f.mime_type,
            size_bytes=f.size_bytes, uploaded_by=uploaded_by,
        ))


async def create_portal_ticket(session: AsyncSession, *, requester_name: str, requester_email: str,
                               subject: str, description: str, category: str | None,
                               files: list[StoredFile] | None) -> Ticket:
    now = _utcnow()
    priority = "MEDIUM"  # portal tickets are MEDIUM (design spec 8 note: no priority picker on the public portal)
    ticket = Ticket(
        ticket_code=await unique_ticket_code(session),
        requester_name=requester_name.strip(),
        requester_email=_norm_email(requester_email),
        subject=subject.strip(),
        description=description.strip(),
        category=category,
        priority=priority,
        status=TicketStatus.OPEN.value,
        team_id=None, assigned_to=None, version=1,
    )
    policy = await _active_sla_for_priority(session, priority, now)
    if policy is not None:
        ticket.sla_policy_id = policy.id
        ticket.first_response_due_at = now + timedelta(minutes=policy.first_response_minutes)
        ticket.resolution_due_at = now + timedelta(minutes=policy.resolution_minutes)
    session.add(ticket)
    await session.flush()
    if files:
        _add_attachment_rows(session, ticket_id=ticket.id, files=files, comment_id=None, uploaded_by=None)
    await write_audit(session, action="TICKET_CREATED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      entity_id=ticket.id, metadata={"ticket_code": ticket.ticket_code, "priority": priority})
    await session.commit()
    await session.refresh(ticket)
    return ticket


# ---- writes (optimistic lock: expected_version must equal ticket.version) -----


async def update_ticket(session: AsyncSession, *, ticket: Ticket, actor: User, changes: dict,
                        reason: str | None, expected_version: int) -> Ticket:
    _ensure_version(ticket, expected_version)
    for field, new in changes.items():
        if new is None and field != "category":
            # Only `category` may be cleared to NULL; the rest are non-nullable.
            raise AppError(422, "VALIDATION_ERROR", "Giá trị không được để trống.")
        old = getattr(ticket, field)
        if old == new:
            continue
        setattr(ticket, field, new)
        _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="FIELD_UPDATED",
                     field_name=field, old_value=old, new_value=new, reason=reason)
    ticket.version += 1
    await write_audit(session, action="TICKET_UPDATED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      actor_id=actor.id, entity_id=ticket.id, metadata={"fields": sorted(changes)})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def change_status(session: AsyncSession, *, ticket: Ticket, actor: User, target: str,
                        reason: str | None, expected_version: int) -> Ticket:
    current = ticket.status
    _ensure_version(ticket, expected_version)
    if not can_transition(current, target):
        raise AppError(400, "INVALID_STATUS_TRANSITION",
                       f"Không thể chuyển trạng thái từ {current} sang {target}.")
    if is_reopen(current, target) and not (reason and reason.strip()):
        raise AppError(400, "INVALID_STATUS_TRANSITION",
                       "Cần nhập lý do để mở lại vé đã giải quyết/đã đóng (FR-TIC-11).")
    now = _utcnow()
    policy = await session.get(SlaPolicy, ticket.sla_policy_id) if ticket.sla_policy_id else None

    # Pause-on-pending resume: extend deadlines by the time the ticket sat in PENDING
    # (Controller decision 3, SRS FR-SLA 'deadline được bù thêm').
    if current == TicketStatus.PENDING.value and target == TicketStatus.IN_PROGRESS.value:
        pending_since = _pending_since(ticket)
        if policy is not None and policy.pause_on_pending and pending_since is not None and pending_since < now:
            pause_seconds = (now - pending_since).total_seconds()
            if pause_seconds > 0:
                extended = []
                if ticket.resolution_due_at is not None:
                    ticket.resolution_due_at = extend_deadline(ticket.resolution_due_at, pause_seconds)
                    extended.append("resolution_due_at")
                if ticket.first_response_due_at is not None and ticket.first_response_at is None:
                    ticket.first_response_due_at = extend_deadline(ticket.first_response_due_at, pause_seconds)
                    extended.append("first_response_due_at")
                if extended:
                    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="FIELD_UPDATED",
                                 field_name="sla_deadlines_extended", old_value=None,
                                 new_value={"pause_seconds": round(pause_seconds), "fields": extended},
                                 reason="Bù thời gian chờ khách hàng (SLA pause_on_pending).")

    # Closure fields (decision 5).
    if target == TicketStatus.RESOLVED.value:
        ticket.resolved_at = now
    elif target == TicketStatus.CLOSED.value:
        ticket.closed_at = now
    if is_reopen(current, target):
        ticket.resolved_at = None
        ticket.closed_at = None

    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="STATUS_CHANGED",
                 field_name="status", old_value=current, new_value=target, reason=reason)
    ticket.status = target
    ticket.version += 1
    await write_audit(session, action="TICKET_STATUS_CHANGED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"from": current, "to": target})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def assign_ticket(session: AsyncSession, *, ticket: Ticket, actor: User, team_id, assigned_to,
                        reason: str | None, expected_version: int) -> Ticket:
    _ensure_version(ticket, expected_version)
    try:
        team_uuid = uuid.UUID(str(team_id))
        assignee_uuid = uuid.UUID(str(assigned_to)) if assigned_to else None
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Nhóm hỗ trợ hoặc nhân viên không tồn tại.")

    # MANAGER may only assign into a team they manage (Controller decision 1).
    if actor.role == UserRole.MANAGER.value:
        allowed = await session.execute(
            select(TeamMember.id).where(
                TeamMember.team_id == team_uuid, TeamMember.user_id == actor.id,
                TeamMember.team_role == "MANAGER", TeamMember.is_active.is_(True),
            )
        )
        if allowed.scalar_one_or_none() is None:
            raise AppError(403, "ACCESS_DENIED", "Bạn chỉ có thể gán vé vào nhóm mình quản lý.")

    team = await session.get(SupportTeam, team_uuid)
    if team is None or not team.is_active:
        raise AppError(404, "NOT_FOUND", "Nhóm hỗ trợ không tồn tại hoặc đã bị vô hiệu hóa.")

    if assignee_uuid is not None:
        membership = await session.execute(
            select(TeamMember.id).where(
                TeamMember.team_id == team_uuid, TeamMember.user_id == assignee_uuid,
                TeamMember.is_active.is_(True),
            )
        )
        if membership.scalar_one_or_none() is None:
            raise AppError(400, "ASSIGNEE_NOT_IN_TEAM",
                           "Người được gán phải là thành viên đang hoạt động của nhóm đã chọn.")

    old_snapshot = {"team_id": str(ticket.team_id) if ticket.team_id else None,
                    "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None}
    ticket.team_id = team_uuid
    ticket.assigned_to = assignee_uuid
    ticket.version += 1
    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="ASSIGNED",
                 field_name=None, old_value=old_snapshot,
                 new_value={"team_id": str(team_uuid), "assigned_to": str(assignee_uuid) if assignee_uuid else None},
                 reason=reason)
    await write_audit(session, action="TICKET_ASSIGNED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      actor_id=actor.id, entity_id=ticket.id,
                      metadata={"team_id": str(team_uuid), "assigned_to": str(assignee_uuid) if assignee_uuid else None})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def add_comment(session: AsyncSession, *, ticket: Ticket, actor: User, content: str,
                      visibility: str, files: list[StoredFile] | None) -> Comment:
    body = content.strip()
    if not body:
        raise AppError(422, "VALIDATION_ERROR", "Nội dung bình luận không được để trống.")
    if visibility not in ("PUBLIC", "INTERNAL"):
        raise AppError(422, "VALIDATION_ERROR", "visibility phải là PUBLIC hoặc INTERNAL.")
    now = _utcnow()
    comment = Comment(ticket_id=ticket.id, author_id=actor.id, content=body,
                      visibility=visibility, source=CommentSource.HUMAN.value)
    session.add(comment)
    await session.flush()
    if files:
        _add_attachment_rows(session, ticket_id=ticket.id, files=files, comment_id=comment.id, uploaded_by=actor.id)
    # The first PUBLIC staff reply counts as the first response (SRS FR-SLA).
    if visibility == "PUBLIC" and ticket.first_response_at is None:
        ticket.first_response_at = now
        ticket.version += 1
    await write_audit(session, action="TICKET_COMMENT_ADDED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"visibility": visibility, "public_first_response": ticket.first_response_at is not None})
    await session.commit()
    await session.refresh(comment)
    return comment


async def add_attachments(session: AsyncSession, *, ticket: Ticket, actor: User, files: list[StoredFile]) -> list[Attachment]:
    rows = []
    for f in files:
        row = Attachment(ticket_id=ticket.id, comment_id=None, original_name=f.original_name,
                         stored_name=f.stored_name, storage_path=f.storage_path, mime_type=f.mime_type,
                         size_bytes=f.size_bytes, uploaded_by=actor.id)
        session.add(row)
        rows.append(row)
    await write_audit(session, action="TICKET_ATTACHMENTS_ADDED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"count": len(files)})
    await session.commit()
    for row in rows:
        await session.refresh(row)
    return rows


# ---- public track --------------------------------------------------------------


async def track_public(session: AsyncSession, *, email: str, ticket_code: str) -> Ticket:
    """Return a ticket only when BOTH code and (normalized) email match (FR-PUB-09).

    Wrong code, wrong email and unknown code share ONE 404 TICKET_NOT_FOUND body so
    the endpoint never confirms whether a code exists.
    """
    ticket = (
        await session.execute(
            select(Ticket).where(
                Ticket.ticket_code == ticket_code.strip().upper(),
                Ticket.requester_email == _norm_email(email),
            )
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND",
                       "Không tìm thấy vé với mã và email đã cung cấp.")
    await write_audit(session, action="TICKET_TRACKED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, entity_id=ticket.id,
                      metadata={"ticket_code": ticket.ticket_code})
    await session.commit()
    return ticket
```

- [ ] **Step 4: Run the integration tests to verify they pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" .venv/Scripts/python -m pytest tests/integration/test_ticket_service.py -q`
Expected: all pass (the 7 flows above). If a seeded-SLA assumption fails (e.g. no MEDIUM policy is active), the create test reveals it — check the seeded `sla_policies` rows first.

- [ ] **Step 5: Run the full unit suite once more**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: all pass (unit tests stay DB-free; importing `app.services.ticket_service` only builds the engine object lazily).

- [ ] **Step 6: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/services/ticket_service.py backend/tests/integration/test_ticket_service.py
git commit -m "feat(backend): ticket service (scoping, create/update/status/assign, comments, SLA pause)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: HTTP layer — public router + staff tickets router + main.py wiring + ASGI integration tests

**Why one task:** the routers are thin parse/map shells over the Task 3 service (mirroring S1 `auth.py`), and `main.py` must mount them in one pass. Task 3 already integration-tested every business rule at service level; this task adds the HTTP harness once (env → `cache_clear` → import `app.main`) so the *wiring* — multipart, scope-through-dependency, the anti-leak 404s, file download — is proven end-to-end over the real DB.

**Files:**
- Create: `backend/app/api/public.py`
- Create: `backend/app/api/tickets.py`
- Modify: `backend/app/services/storage.py` (add one shared helper, below)
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_http_tickets.py`

**Interfaces:**
- Consumes: Task 2 `schemas.public` / `schemas.ticket` + `storage.store_upload/resolve_upload/remove_stored`; Task 1 `parse_allowed_extensions`; Task 3 `ticket_service.*` exact signatures; S1 `require_roles`/`get_current_user`.
- Produces (Task 5/6 frontend calls these exact paths/shapes):
  - `POST /api/public/tickets` (multipart: `requester_name`, `requester_email`, `subject`, `description`, `category?`, `files?`) → 201 `PortalTicketOut`
  - `POST /api/public/track` (JSON `PortalTrackRequest`) → `PortalTrackResponse`
  - `GET /api/tickets?page&page_size&status&q&assigned_to_me` → `TicketListResponse` (staff)
  - `GET /api/tickets/{ticket_id}` → `TicketDetail`
  - `PATCH /api/tickets/{ticket_id}` (JSON `TicketUpdateRequest`) → `TicketDetail`
  - `POST /api/tickets/{ticket_id}/status` (JSON `StatusUpdateRequest`) → `TicketDetail`
  - `POST /api/tickets/{ticket_id}/assign` (JSON `AssignRequest`, MANAGER/ADMIN) → `TicketDetail`
  - `POST /api/tickets/{ticket_id}/comments` (multipart: `content`, `visibility=PUBLIC|INTERNAL`, `files?`) → `TicketDetail`
  - `POST /api/tickets/{ticket_id}/attachments` (multipart `files` ≥1) → `TicketDetail`
  - `GET /api/teams` (MANAGER/ADMIN) → `list[TeamOut]`
  - `GET /api/attachments/{attachment_id}/download` → file bytes
  - `storage.store_many(uploads, *, upload_dir, allowed, max_bytes, max_files) -> list[StoredFile]` (raises 422 `VALIDATION_ERROR` when `len(uploads) > max_files`; cleans already-written files on failure)

- [ ] **Step 1: Add the shared `store_many` helper**

Append to `backend/app/services/storage.py`:

```python
async def store_many(
    uploads, *, upload_dir: Path, allowed: set[str], max_bytes: int, max_files: int
) -> list[StoredFile]:
    """Validate the whole batch up front, then store each file.

    The count limit is checked BEFORE anything is written (SRS file rule '<= 5 tệp
    mỗi yêu cầu' -> 422 VALIDATION_ERROR). If any single file is rejected mid-way,
    the files already written are removed so a failed request never leaks bytes.
    """
    if uploads is None:
        return []
    if len(uploads) > max_files:
        raise AppError(422, "VALIDATION_ERROR", f"Mỗi yêu cầu tối đa {max_files} tệp đính kèm.")
    stored: list[StoredFile] = []
    try:
        for up in uploads:
            stored.append(await store_upload(up, upload_dir=upload_dir, allowed=allowed, max_bytes=max_bytes))
    except Exception:
        for sf in stored:
            remove_stored(sf.storage_path)
        raise
    return stored
```

- [ ] **Step 2: Implement the public router**

Create `backend/app/api/public.py`:

```python
"""Public portal API — no auth (SRS FR-PUB). Create a ticket (+ optional files),
and look one up by code+email. Both are rate-limited in S2 (Controller decision 4).
Wrong code / wrong email / unknown code share ONE 404 body (FR-PUB-09 anti-leak);
errors keep the uniform {error_code, message, details} envelope (SRS 5.2/10.2).
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.schemas.public import (
    PortalCommentOut,
    PortalCreateRequest,
    PortalTicketOut,
    PortalTrackRequest,
    PortalTrackResponse,
)
from app.services import ticket_service
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import remove_stored, store_many

router = APIRouter(tags=["public"])

# Rate strings are read once at import time. Integration runs set
# RATE_LIMIT_ENABLED=false (and cache_clear) BEFORE importing app.main, so this
# module always sees a Settings built with the intended env (config.py).
_settings = get_settings()


async def _store_and_rollback(files) -> list:
    """Store attachments to disk; the caller must remove them if the DB write fails."""
    return await store_many(
        files,
        upload_dir=Path(_settings.upload_dir),
        allowed=parse_allowed_extensions(_settings.allowed_file_types),
        max_bytes=_settings.max_upload_size_mb * 1024 * 1024,
        max_files=_settings.upload_max_files,
    )


@router.post("/tickets", response_model=PortalTicketOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.public_create_rate)
async def create_ticket(
    request: Request,
    requester_name: str = Form(...),
    requester_email: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    category: str | None = Form(default=None),
    files: Annotated[list[UploadFile] | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> PortalTicketOut:
    # Re-validate the free-form multipart fields through the schema so the SRS 10.1
    # rules (name 2-100, email format, subject 5-200, description 10-20000,
    # category in the enum) live in exactly one place.
    try:
        payload = PortalCreateRequest(
            requester_name=requester_name, requester_email=requester_email,
            subject=subject, description=description, category=category,
        )
    except ValidationError as exc:
        raise AppError(422, "VALIDATION_ERROR", "Dữ liệu không hợp lệ.",
                       details=jsonable_encoder(exc.errors()))
    stored = await _store_and_rollback(files)
    try:
        ticket = await ticket_service.create_portal_ticket(
            session, requester_name=payload.requester_name, requester_email=payload.requester_email,
            subject=payload.subject, description=payload.description, category=payload.category,
            files=stored or None,
        )
    except Exception:
        for sf in stored:
            remove_stored(sf.storage_path)
        raise
    return PortalTicketOut(ticket_code=ticket.ticket_code, status=ticket.status,
                           subject=ticket.subject, created_at=ticket.created_at)


@router.post("/track", response_model=PortalTrackResponse)
@limiter.limit(_settings.public_track_rate)
async def track_ticket(
    payload: PortalTrackRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PortalTrackResponse:
    ticket = await ticket_service.track_public(session, email=payload.email, ticket_code=payload.ticket_code)
    public_comments = sorted(
        (c for c in ticket.comments if c.visibility == "PUBLIC" and c.deleted_at is None),
        key=lambda c: c.created_at,
    )
    return PortalTrackResponse(
        ticket_code=ticket.ticket_code, subject=ticket.subject, status=ticket.status,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
        comments=[PortalCommentOut(id=str(c.id), content=c.content, created_at=c.created_at)
                  for c in public_comments],
    )
```

- [ ] **Step 3: Implement the staff tickets router**

Create `backend/app/api/tickets.py`:

```python
"""Staff ticket API (SRS 8.2) — every route depends on require_roles so RBAC runs
in the dependency layer, then the Task 3 service applies per-record scoping with
the anti-leak 404 (out-of-scope == not found). Writes echo `version`; stale reads
return 409 VERSION_CONFLICT. All staff roles reach list/detail/update/status/
comments/attachments; assign + the team picker are MANAGER/ADMIN (Controller
decision 1). Staff may attach up to 5 files (SRS file rules).
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_roles
from app.core.errors import AppError
from app.db.session import get_session
from app.models.ticket import Attachment, Ticket
from app.models.user import User
from app.schemas.ticket import (
    AssignRequest,
    AttachmentOut,
    CommentOut,
    HistoryOut,
    StatusUpdateRequest,
    TeamMemberOut,
    TeamOut,
    TicketDetail,
    TicketListItem,
    TicketListResponse,
    TicketUpdateRequest,
)
from app.services import ticket_service
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import remove_stored, resolve_upload, store_many

router = APIRouter(tags=["tickets"])

STAFF = ("AGENT", "MANAGER", "ADMIN")
MANAGER_ADMIN = ("MANAGER", "ADMIN")

_settings = get_settings()


async def _store_and_rollback(files) -> list:
    return await store_many(
        files,
        upload_dir=Path(_settings.upload_dir),
        allowed=parse_allowed_extensions(_settings.allowed_file_types),
        max_bytes=_settings.max_upload_size_mb * 1024 * 1024,
        max_files=_settings.upload_max_files,
    )


async def _rollback(stored) -> None:
    for sf in stored:
        remove_stored(sf.storage_path)


# ---- response mappers (mirror auth.py's to_user_out) --------------------------


async def _author_names(session: AsyncSession, comments) -> dict[str, str]:
    ids = {c.author_id for c in comments if c.author_id}
    if not ids:
        return {}
    rows = (await session.execute(select(User.full_name, User.id).where(User.id.in_(ids)))).all()
    return {str(uid): name for name, uid in rows}


async def _to_detail(session: AsyncSession, ticket: Ticket) -> TicketDetail:
    comments = [c for c in ticket.comments if c.deleted_at is None]
    comments.sort(key=lambda c: c.created_at)
    authors = await _author_names(session, comments)
    attachments = sorted((a for a in ticket.attachments if a.deleted_at is None),
                         key=lambda a: a.created_at)
    history = sorted(ticket.history, key=lambda h: h.created_at, reverse=True)

    def _s(v) -> str | None:
        return str(v) if v else None

    return TicketDetail(
        id=str(ticket.id), ticket_code=ticket.ticket_code,
        requester_name=ticket.requester_name, requester_email=ticket.requester_email,
        subject=ticket.subject, description=ticket.description,
        category=ticket.category, priority=ticket.priority, status=ticket.status,
        team_id=_s(ticket.team_id), assigned_to=_s(ticket.assigned_to),
        sla_policy_id=_s(ticket.sla_policy_id),
        first_response_due_at=ticket.first_response_due_at, resolution_due_at=ticket.resolution_due_at,
        first_response_at=ticket.first_response_at, resolved_at=ticket.resolved_at, closed_at=ticket.closed_at,
        version=ticket.version, created_at=ticket.created_at, updated_at=ticket.updated_at,
        comments=[CommentOut(id=str(c.id), author_id=_s(c.author_id),
                             author_name=authors.get(str(c.author_id)) if c.author_id else None,
                             content=c.content, visibility=c.visibility, source=c.source,
                             created_at=c.created_at, edited_at=c.edited_at) for c in comments],
        attachments=[AttachmentOut(id=str(a.id), original_name=a.original_name, mime_type=a.mime_type,
                                   size_bytes=a.size_bytes, created_at=a.created_at,
                                   uploaded_by=_s(a.uploaded_by)) for a in attachments],
        history=[HistoryOut(id=str(h.id), event_type=h.event_type, field_name=h.field_name,
                            old_value=h.old_value, new_value=h.new_value,
                            changed_by=_s(h.changed_by), reason=h.reason, created_at=h.created_at)
                 for h in history],
    )


async def _detail_after_write(session: AsyncSession, ticket: Ticket) -> TicketDetail:
    """Service returns an entity whose collection relationships are stale after new
    children (comments/attachments/history) were added; reload for the response."""
    fresh = await session.get(Ticket, ticket.id)
    return await _to_detail(session, fresh)


# ---- read ----------------------------------------------------------------------


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(default=None, pattern="^(OPEN|IN_PROGRESS|PENDING|RESOLVED|CLOSED)$"),
    q: str | None = Query(default=None, max_length=100),
    assigned_to_me: bool = Query(False),
) -> TicketListResponse:
    total, items = await ticket_service.list_tickets(
        session, user=user, page=page, page_size=page_size, status=status, q=q, assigned_to_me=assigned_to_me,
    )
    return TicketListResponse(items=[TicketListItem(**it) for it in items],
                              total=total, page=page, page_size=page_size)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    return await _to_detail(session, ticket)


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(
    user: User = Depends(require_roles(*MANAGER_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[TeamOut]:
    pairs = await ticket_service.teams_with_members(session, user=user)
    return [
        TeamOut(id=str(team.id), name=team.name, members=[
            TeamMemberOut(id=str(m.user.id), full_name=m.user.full_name, team_role=m.team_role)
            for m in members if m.user is not None
        ])
        for team, members in pairs
    ]


# ---- writes --------------------------------------------------------------------


@router.patch("/tickets/{ticket_id}", response_model=TicketDetail)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdateRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    changes = {f: getattr(payload, f) for f in payload.model_fields_set if f not in ("reason", "version")}
    ticket = await ticket_service.update_ticket(session, ticket=ticket, actor=user,
                                                changes=changes, reason=payload.reason,
                                                expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/status", response_model=TicketDetail)
async def change_status(
    ticket_id: str,
    payload: StatusUpdateRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    ticket = await ticket_service.change_status(session, ticket=ticket, actor=user,
                                                target=payload.status, reason=payload.reason,
                                                expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketDetail)
async def assign_ticket(
    ticket_id: str,
    payload: AssignRequest,
    user: User = Depends(require_roles(*MANAGER_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    ticket = await ticket_service.assign_ticket(session, ticket=ticket, actor=user,
                                                team_id=payload.team_id, assigned_to=payload.assigned_to,
                                                reason=payload.reason, expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/comments", response_model=TicketDetail)
async def add_comment(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    content: str = Form(..., min_length=1, max_length=10000),
    visibility: str = Form(default="PUBLIC"),
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    stored = await _store_and_rollback(files)
    try:
        await ticket_service.add_comment(session, ticket=ticket, actor=user, content=content,
                                         visibility=visibility, files=stored or None)
    except Exception:
        await _rollback(stored)
        raise
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketDetail)
async def add_attachments(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    files: Annotated[list[UploadFile], File()],
) -> TicketDetail:
    # files is required here (≥1 per SRS file rules); the comment route keeps it optional.
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    stored = await _store_and_rollback(files)
    try:
        await ticket_service.add_attachments(session, ticket=ticket, actor=user, files=stored)
    except Exception:
        await _rollback(stored)
        raise
    return await _detail_after_write(session, ticket)


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    try:
        aid = uuid.UUID(attachment_id)
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại.")
    row = (await session.execute(
        select(Attachment).where(Attachment.id == aid, Attachment.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại.")
    # Scope gate reuses the anti-leak 404: a staff user who cannot see the parent
    # ticket cannot learn the file exists either.
    await ticket_service.get_scoped_ticket(session, user=user, ticket_id=row.ticket_id)
    path = resolve_upload(row.storage_path)
    if not path.is_file():
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại trên máy chủ.")
    return FileResponse(path, media_type=row.mime_type, filename=row.original_name)
```

- [ ] **Step 4: Wire routers + rate limit into main.py**

Modify `backend/app/main.py` (add imports after the auth import; add includes before `register_exception_handlers`):

```python
from app.api.public import router as public_router
from app.api.tickets import router as tickets_router
```
and:
```python
    application.include_router(public_router, prefix="/api/public")
    application.include_router(tickets_router, prefix="/api")

    # slowapi limiter bound to Settings.rate_limit_enabled (S2 public endpoints).
    init_rate_limit(application)

    # Standard JSON error body {error_code, message, details} on every HTTP error.
    register_exception_handlers(application)
```
Add `from app.core.rate_limit import init_rate_limit` to the `app.core.*` imports.

- [ ] **Step 5: Write the ASGI integration tests**

Create `backend/tests/integration/test_http_tickets.py`:

```python
"""HTTP-level integration: routers wired in app.main over the real compose DB.

Run with the S0 acceptance stack up and, in ONE command so the env is present
before any app import:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support \
  RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_http_tickets.py -q

This module additionally forces RATE_LIMIT_ENABLED=false and clears the cached
Settings before importing app.main, so an accidental run never trips slowapi and
never targets the default :5432 database. Each test builds a throwaway org and
removes exactly what it created (users/team/ticket + uploaded bytes).
"""

import os
import uuid
from pathlib import Path

os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("AI_PROVIDER", "mock")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
get_settings.cache_clear()

from app.core.errors import AppError  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.enums import TeamRole, UserRole  # noqa: E402
from app.models.team import SupportTeam, TeamMember  # noqa: E402
from app.models.ticket import Attachment, Ticket  # noqa: E402
from app.models.user import RefreshToken, User  # noqa: E402
from app.services import auth_service, ticket_service  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)

_PASSWORD = "It@123456"


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


@pytest.fixture(scope="module")
async def _client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _tag() -> str:
    return uuid.uuid4().hex[:12]


async def _add_user(email, full_name, role) -> User:
    async with AsyncSessionLocal() as s:
        u = User(full_name=full_name, email=email, password_hash=hash_password(_PASSWORD),
                 role=role, is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _create_org():
    tag = _tag()
    admin = await _add_user(f"admin.{tag}@example.com", "Admin HTTP", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý HTTP", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A HTTP", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B HTTP", UserRole.AGENT.value)
    async with AsyncSessionLocal() as s:
        team_a = SupportTeam(name=f"Team A HTTP {tag}", description="http test")
        s.add(team_a)
        await s.flush()
        team_b = SupportTeam(name=f"Team B HTTP {tag}", description="http test")
        s.add(team_b)
        await s.flush()
        s.add(TeamMember(team_id=team_a.id, user_id=manager.id, team_role=TeamRole.MANAGER.value, is_active=True))
        s.add(TeamMember(team_id=team_a.id, user_id=agent_a.id, team_role=TeamRole.MEMBER.value, is_active=True))
        s.add(TeamMember(team_id=team_b.id, user_id=agent_b.id, team_role=TeamRole.MEMBER.value, is_active=True))
        await s.commit()
    return {"admin": admin, "manager": manager, "agent_a": agent_a, "agent_b": agent_b,
            "team_a": team_a, "team_b": team_b,
            "user_ids": [admin.id, manager.id, agent_a.id, agent_b.id]}


async def _token(user: User) -> str:
    async with AsyncSessionLocal() as s:
        result = await auth_service.login(s, email=user.email, password=_PASSWORD,
                                          ip_address="127.0.0.1", user_agent="pytest")
        return result.access_token


async def _remove_ticket_files(ticket_id) -> None:
    """Unlink any stored bytes for a ticket's attachments before the row is deleted.

    Deleting the Attachment rows (via the Ticket FK cascade) would strand the files
    in backend/uploads; Task 7 adds backend/uploads/ to .gitignore either way.
    """
    async with AsyncSessionLocal() as s:
        paths = (await s.execute(
            select(Attachment.storage_path).where(Attachment.ticket_id == ticket_id)
        )).scalars().all()
        for p in paths:
            Path(p).unlink(missing_ok=True)


async def _cleanup_org(org, ticket_ids) -> None:
    ids = list(ticket_ids)
    user_ids = org["user_ids"]
    team_ids = [org["team_a"].id, org["team_b"].id]
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        if ids:
            await s.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
            await s.execute(delete(Ticket).where(Ticket.id.in_(ids)))  # cascades comments/history/attachments
        await s.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


async def _public_create(client, **data):
    return await client.post("/api/public/tickets", data=data)
```

```python
async def test_public_create_track_and_staff_comment_visibility(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = await _public_create(client, requester_name="Khách HTTP", requester_email="khach.http@example.com",
                                 subject="Không gửi được báo cáo", description="Bấm nút gửi không có phản hồi.")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["ticket_code"].startswith("TK-") and body["status"] == "OPEN"
        code = body["ticket_code"]

        # Staff replies PUBLIC + INTERNAL.
        async with AsyncSessionLocal() as s:
            ticket = await ticket_service.track_public(s, email="khach.http@example.com", ticket_code=code)
            ticket_id = ticket.id
        r1 = await client.post(f"/api/tickets/{ticket_id}/comments", headers=headers,
                               data={"content": "Chúng tôi đang xử lý.", "visibility": "PUBLIC"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["first_response_at"] is not None
        r2 = await client.post(f"/api/tickets/{ticket_id}/comments", headers=headers,
                               data={"content": "Nội bộ: kiểm tra log.", "visibility": "INTERNAL"})
        assert r2.status_code == 200, r2.text

        # Public track only surfaces the PUBLIC reply.
        r3 = await client.post("/api/public/track",
                               json={"email": "khach.http@example.com", "ticket_code": code})
        assert r3.status_code == 200, r3.text
        assert len(r3.json()["comments"]) == 1
        assert r3.json()["comments"][0]["content"].startswith("Chúng tôi")

        # Wrong email is the same generic 404.
        r4 = await client.post("/api/public/track",
                               json={"email": "other@example.com", "ticket_code": code})
        assert r4.status_code == 404 and r4.json()["error_code"] == "TICKET_NOT_FOUND"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_assign_scope_and_listing(client):
    org = await _create_org()
    try:
        r = await _public_create(client, requester_name="Khách Gán", requester_email="khach.gan@example.com",
                                 subject="Cần hỗ trợ gấp", description="Mô tả đủ dài để tạo vé qua cổng công khai.")
        code = r.json()["ticket_code"]
        async with AsyncSessionLocal() as s:
            t = await ticket_service.track_public(s, email="khach.gan@example.com", ticket_code=code)
            ticket_id = t.id

        admin_tok = await _token(org["admin"])
        detail = await client.get(f"/api/tickets/{ticket_id}", headers={"Authorization": f"Bearer {admin_tok}"})
        assert detail.status_code == 200 and detail.json()["team_id"] is None

        mgr_tok = await _token(org["manager"])
        agent_b_tok = await _token(org["agent_b"])
        # agent_b (team B, not assigned) cannot see the unassigned ticket -> 404.
        denied = await client.get(f"/api/tickets/{ticket_id}", headers={"Authorization": f"Bearer {agent_b_tok}"})
        assert denied.status_code == 404 and denied.json()["error_code"] == "TICKET_NOT_FOUND"

        assign = await client.post(
            f"/api/tickets/{ticket_id}/assign", headers={"Authorization": f"Bearer {mgr_tok}"},
            json={"team_id": str(org["team_a"].id), "assigned_to": str(org["agent_a"].id),
                  "version": detail.json()["version"]},
        )
        assert assign.status_code == 200, assign.text
        assert assign.json()["team_id"] == str(org["team_a"].id)
        assert assign.json()["assigned_to"] == str(org["agent_a"].id)

        agent_a_tok = await _token(org["agent_a"])
        ok = await client.get(f"/api/tickets/{ticket_id}", headers={"Authorization": f"Bearer {agent_a_tok}"})
        assert ok.status_code == 200

        # Manager list includes the ticket; agent_b list excludes it.
        lst = await client.get("/api/tickets", headers={"Authorization": f"Bearer {mgr_tok}"})
        assert any(i["id"] == str(ticket_id) for i in lst.json()["items"])
        lst_b = await client.get("/api/tickets", headers={"Authorization": f"Bearer {agent_b_tok}"})
        assert all(i["id"] != str(ticket_id) for i in lst_b.json()["items"])
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_public_validation_error_envelope_and_version_conflict(client):
    org = await _create_org()
    try:
        r = await _public_create(client, requester_name="X", requester_email="khach.validation@example.com",
                                 subject="Quá ngắn", description="Mô tả ngắn.")
        assert r.status_code == 422 and r.json()["error_code"] == "VALIDATION_ERROR"

        admin_tok = await _token(org["admin"])
        headers = {"Authorization": f"Bearer {admin_tok}"}
        rr = await _public_create(client, requester_name="Khách Phiên bản", requester_email="khach.ver@example.com",
                                  subject="Kiểm tra xung đột phiên bản", description="Mô tả đủ dài cho vé này.")
        async with AsyncSessionLocal() as s:
            t = await ticket_service.track_public(s, email="khach.ver@example.com", ticket_code=rr.json()["ticket_code"])
            ticket_id = t.id
        d1 = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        v1 = d1.json()["version"]
        d2 = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        # Stale version => 409 VERSION_CONFLICT.
        stale = await client.post(f"/api/tickets/{ticket_id}/status", headers=headers,
                                  json={"status": "IN_PROGRESS", "version": v1})
        assert stale.status_code == 409 and stale.json()["error_code"] == "VERSION_CONFLICT"
        # Fresh version succeeds.
        ok = await client.post(f"/api/tickets/{ticket_id}/status", headers=headers,
                               json={"status": "IN_PROGRESS", "version": d2.json()["version"]})
        assert ok.status_code == 200 and ok.json()["status"] == "IN_PROGRESS"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_attachment_upload_and_download_scope(client):
    org = await _create_org()
    mgr_tok = await _token(org["manager"])
    admin_tok = await _token(org["admin"])
    try:
        r = await _public_create(client, requester_name="Khách Tệp", requester_email="khach.file@example.com",
                                 subject="Gửi tệp báo lỗi", description="Tôi đính kèm tệp log cho lỗi này.")
        code = r.json()["ticket_code"]
        async with AsyncSessionLocal() as s:
            t = await ticket_service.track_public(s, email="khach.file@example.com", ticket_code=code)
            ticket_id = t.id

        up = await client.post(
            f"/api/tickets/{ticket_id}/comments",
            headers={"Authorization": f"Bearer {mgr_tok}"},
            data={"content": "Đã nhận tệp log.", "visibility": "INTERNAL"},
            files={"files": ("log.txt", b"ERR 500 on submit", "text/plain")},
        )
        assert up.status_code == 200, up.text
        attachment = up.json()["attachments"][0]
        assert attachment["original_name"] == "log.txt"

        got = await client.get(f"/api/attachments/{attachment['id']}/download",
                               headers={"Authorization": f"Bearer {mgr_tok}"})
        assert got.status_code == 200 and got.content == b"ERR 500 on submit"

        # Out-of-scope staff get the same 404, not the bytes.
        agent_b_tok = await _token(org["agent_b"])
        denied = await client.get(f"/api/attachments/{attachment['id']}/download",
                                  headers={"Authorization": f"Bearer {agent_b_tok}"})
        assert denied.status_code == 404

        # The extra PUBLIC comment above also proves the file attach carried over.
        detail = await client.get(f"/api/tickets/{ticket_id}",
                                  headers={"Authorization": f"Bearer {admin_tok}"})
        assert detail.status_code == 200
    finally:
        await _remove_ticket_files(ticket_id)
        await _cleanup_org(org, [ticket_id])
```

> Note for the implementer: keep every `data=`/`files=` pair as shown. `_public_create` posts `data=` (urlencoded form). When files are absent the endpoint still parses the form fields; when files are present `httpx` switches the request to `multipart/form-data` automatically — FastAPI handles both. Keep the file's top section ordered: set `RATE_LIMIT_ENABLED=false` **before** `get_settings.cache_clear()` and the `app.main` import (the current draft is already ordered this way).

- [ ] **Step 6: Run the unit suite (no regressions), then the integration suite**

Run unit: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: all pass (58 total now).

Run integration (compose DB up on :5433):
`cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_http_tickets.py tests/integration/test_ticket_service.py -q`
Expected: all pass (Task 3's 7 service flows + these 4 HTTP flows). If a 429 ever appears, the run env is not applying `RATE_LIMIT_ENABLED=false` — confirm the variable reached the Settings (`settings.rate_limit_enabled is False`).

- [ ] **Step 7: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/api/public.py backend/app/api/tickets.py backend/app/services/storage.py backend/app/main.py backend/tests/integration/test_http_tickets.py
git commit -m "feat(backend): S2 public + staff ticket HTTP API, main.py wiring, ASGI integration tests

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Frontend foundation + Public Portal (create & track)

**Why one task:** the Public Portal is the customer-facing surface of S2 (design spec §6.2 routes `/` and `/track`). It needs three small foundations first — a `multipart` + file-download pair on the API client, a Vietnamese label/format helper module (UI always Vietnamese, identifiers English — Global Constraint), and route reshuffling that gives the public portal `/` and moves the S0 health page to `/health` (design spec §6.1: `/` = Public Portal form, `/track` = lookup). Backend for all of it landed in Task 4 (`POST /api/public/tickets` multipart, `POST /api/public/track` JSON) — nothing in this task changes the backend.

**Files:**
- Modify: `frontend/src/api/client.js` (add `postForm` + blob download)
- Create: `frontend/src/lib/labels.js`
- Create: `frontend/src/pages/PortalCreatePage.jsx`
- Create: `frontend/src/pages/PortalTrackPage.jsx`
- Create: `frontend/src/styles/portal.css`
- Modify: `frontend/src/App.jsx` (routes `/` + `/track` public; `/health` moved)

**Interfaces:**
- Consumes (Task 4, exact): `POST /api/public/tickets` multipart fields `requester_name|requester_email|subject|description|category?|files?` → 201 `PortalTicketOut{ticket_code,status,subject,created_at}`; `POST /api/public/track` JSON `{email,ticket_code}` → `PortalTrackResponse{ticket_code,subject,status,created_at,updated_at,comments:[{id,content,created_at}]}`. Errors = uniform `{error_code,message,details}`; unknown/mismatch → 404 `TICKET_NOT_FOUND`.
- Consumes (S1): `api.get/post` on `../api/client.js`, `useAuth`, CSS tokens.
- Produces (Task 6 consumes): `api.postForm(path, formData)`, `api.fetchBlob(path)` + `triggerDownload(blob, filename)`; `labels.js` exports `STATUS_LABELS/PRIORITY_LABELS/CATEGORY_LABELS/VISIBILITY_LABELS/labelOf/fmtDateTime`; the route map in `App.jsx` with public `/`, `/track`, `/login`, `/health` and `/app/*` unchanged.

- [ ] **Step 1: Extend the API client with multipart POST + blob download**

Edit `frontend/src/api/client.js`. After `export const api = {...}` add a `postForm` method, and after `export { request };` add the blob helpers:

```js
export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  // multipart: rawFetch already skips the JSON Content-Type for FormData (S2 portal upload).
  postForm: (path, formData) => request(path, { method: 'POST', body: formData }),
  // Binary GET (file download) with the same in-memory Bearer token as the JSON calls.
  fetchBlob: (path) => fetchBlob(path),
};

export { request };

// --- file download (S2 attachments; see TicketDetailPage in Task 6) ----------

export async function fetchBlob(path) {
  const headers = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const res = await fetch(path, { headers, credentials: 'same-origin' });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw toError(res, body);
  }
  return res.blob();
}

export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

> Note: `fetchBlob`/`triggerDownload` are defined after `api` in the same module — `api.fetchBlob` only references them at call time, so function hoisting keeps this valid. The Task 4 public endpoints need no auth header; sending one when a token exists is harmless (public routes ignore it).

- [ ] **Step 2: Create the Vietnamese label/format module**

Create `frontend/src/lib/labels.js`:

```js
// S2 UI copy: identifiers stay English (enum values), display always Vietnamese
// (Global Constraint). Keep maps in sync with backend app/models/enums.py.
export const STATUS_LABELS = {
  OPEN: 'Mở',
  IN_PROGRESS: 'Đang xử lý',
  PENDING: 'Chờ bổ sung thông tin',
  RESOLVED: 'Đã giải quyết',
  CLOSED: 'Đã đóng',
};

export const PRIORITY_LABELS = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  URGENT: 'Khẩn cấp',
};

export const CATEGORY_LABELS = {
  TECHNICAL: 'Kỹ thuật',
  ACCOUNT: 'Tài khoản',
  BILLING: 'Thanh toán',
  GENERAL: 'Chung',
  OTHER: 'Khác',
};

export const VISIBILITY_LABELS = {
  PUBLIC: 'Công khai',
  INTERNAL: 'Nội bộ',
};

export function labelOf(map, value) {
  return (value && map[value]) || value || '—';
}

// UTC ISO 8601 from the API -> local Vietnamese display (Global Constraint).
export function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('vi-VN');
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('vi-VN');
}
```

- [ ] **Step 3: Build the Portal Create page**

Create `frontend/src/pages/PortalCreatePage.jsx`:

```jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import { CATEGORY_LABELS } from '../lib/labels.js';
import '../styles/portal.css';

// SRS 10.1 field rules (mirrored here for inline UX; backend is authoritative).
const MAX_FILES = 5;

function fieldErrors(err) {
  // Uniform envelope: details is a pydantic error list [{loc,msg},...].
  if (!err.details) return err.message;
  const parts = err.details.map((d) => {
    const field = (d.loc || []).filter((s) => typeof s === 'string').join('.');
    return field ? `${field}: ${d.msg}` : d.msg;
  });
  return parts.slice(0, 3).join('; ') || err.message;
}

export default function PortalCreatePage() {
  const [form, setForm] = useState({
    requester_name: '',
    requester_email: '',
    subject: '',
    description: '',
    category: '',
  });
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [created, setCreated] = useState(null); // PortalTicketOut | null

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return; // disable double-submit (SRS 7.1.1)
    if (files.length > MAX_FILES) {
      setFormError(`Mỗi yêu cầu tối đa ${MAX_FILES} tệp đính kèm.`);
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const fd = new FormData();
      fd.append('requester_name', form.requester_name.trim());
      fd.append('requester_email', form.requester_email.trim().toLowerCase());
      fd.append('subject', form.subject.trim());
      fd.append('description', form.description.trim());
      if (form.category) fd.append('category', form.category);
      files.forEach((f) => fd.append('files', f));
      const body = await api.postForm('/api/public/tickets', fd); // 201 PortalTicketOut
      setCreated(body);
    } catch (err) {
      setFormError(err.error_code === 'RATE_LIMITED'
        ? 'Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau.'
        : fieldErrors(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (created) {
    return (
      <div className="portal-page">
        <section className="portal-card portal-success" role="status">
          <h1>Đã tiếp nhận yêu cầu hỗ trợ</h1>
          <p>
            Cảm ơn {created.requester_name || 'bạn'}, yêu cầu đã được ghi nhận.
            Vui lòng lưu lại mã vé để tra cứu tiến độ:
          </p>
          <p className="portal-code" data-testid="created-code">{created.ticket_code}</p>
          <p className="text-muted">Trạng thái hiện tại: {labelOfStatus(created.status)}</p>
          <div className="portal-actions">
            <Link className="btn-primary" to={`/track?code=${encodeURIComponent(created.ticket_code)}`}>
              Tra cứu trạng thái
            </Link>
            <Link className="btn-ghost" to="/">Gửi yêu cầu khác</Link>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="portal-page">
      <section className="portal-card">
        <h1>Gửi yêu cầu hỗ trợ</h1>
        <p className="text-muted">Chúng tôi sẽ phản hồi qua email bạn cung cấp. Vui lòng điền đầy đủ thông tin.</p>

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Họ và tên *</span>
            <input value={form.requester_name} onChange={set('requester_name')}
              required minLength={2} maxLength={100} placeholder="Nguyễn Văn A" />
          </label>

          <label className="field">
            <span>Email *</span>
            <input type="email" value={form.requester_email} onChange={set('requester_email')}
              required maxLength={255} placeholder="ban@example.com" autoComplete="email" />
          </label>

          <label className="field">
            <span>Tiêu đề *</span>
            <input value={form.subject} onChange={set('subject')}
              required minLength={5} maxLength={200} placeholder="Mô tả ngắn vấn đề" />
          </label>

          <label className="field">
            <span>Mô tả chi tiết *</span>
            <textarea rows={6} value={form.description} onChange={set('description')}
              required minLength={10} maxLength={20000} placeholder="Mô tả vấn đề bạn gặp phải, các bước đã thực hiện…" />
          </label>

          <label className="field">
            <span>Phân loại</span>
            <select value={form.category} onChange={set('category')}>
              <option value="">— Chọn phân loại (không bắt buộc) —</option>
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Tệp đính kèm (tối đa {MAX_FILES} tệp, mỗi tệp ≤ 10 MB)</span>
            <input type="file" multiple
              accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
              onChange={(e) => setFiles([...e.target.files])} />
            {files.length > 0 && (
              <small className="text-muted">{files.length} tệp: {files.map((f) => f.name).join(', ')}</small>
            )}
          </label>

          {formError && <p className="form-error" role="alert">{formError}</p>}

          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Đang gửi…' : 'Gửi yêu cầu'}
          </button>
        </form>

        <p className="portal-foot">
          Đã có yêu cầu? <Link to="/track">Tra cứu trạng thái vé</Link> ·{' '}
          Nhân viên? <Link to="/login">Đăng nhập</Link>
        </p>
      </section>
    </div>
  );
}

function labelOfStatus(s) {
  return ({ OPEN: 'Mở', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ bổ sung thông tin', RESOLVED: 'Đã giải quyết', CLOSED: 'Đã đóng' })[s] || s;
}
```

- [ ] **Step 4: Build the Portal Track page**

Create `frontend/src/pages/PortalTrackPage.jsx`:

```jsx
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client.js';
import { fmtDateTime } from '../lib/labels.js';
import '../styles/portal.css';

export default function PortalTrackPage() {
  const [params] = useSearchParams();
  const [form, setForm] = useState({
    ticket_code: params.get('code') || '',
    email: params.get('email') || '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // PortalTrackResponse | null

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const body = await api.post('/api/public/track', {
        ticket_code: form.ticket_code.trim().toUpperCase(),
        email: form.email.trim().toLowerCase(),
      });
      setResult(body);
    } catch (err) {
      if (err.error_code === 'TICKET_NOT_FOUND' || err.status === 404) {
        setError('Không tìm thấy vé với mã và email này. Vui lòng kiểm tra lại.');
      } else {
        setError(err.message || 'Không thể tra cứu. Vui lòng thử lại.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="portal-page">
      <section className="portal-card">
        <h1>Tra cứu yêu cầu hỗ trợ</h1>
        <p className="text-muted">Nhập mã vé và email bạn đã dùng khi gửi yêu cầu.</p>

        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Mã vé *</span>
            <input value={form.ticket_code} onChange={(e) => setForm((f) => ({ ...f, ticket_code: e.target.value }))}
              required placeholder="TK-XXXXXXXX" />
          </label>
          <label className="field">
            <span>Email *</span>
            <input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required placeholder="ban@example.com" autoComplete="email" />
          </label>

          {error && <p className="form-error" role="alert">{error}</p>}

          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Đang tra cứu…' : 'Tra cứu'}
          </button>
        </form>

        {result && (
          <div className="track-result" data-testid="track-result">
            <h2>{result.subject}</h2>
            <dl className="track-meta">
              <div><dt>Mã vé</dt><dd>{result.ticket_code}</dd></div>
              <div><dt>Trạng thái</dt><dd>{labelOfStatus(result.status)}</dd></div>
              <div><dt>Ngày gửi</dt><dd>{fmtDateTime(result.created_at)}</dd></div>
              {result.updated_at && <div><dt>Cập nhật lần cuối</dt><dd>{fmtDateTime(result.updated_at)}</dd></div>}
            </dl>
            {result.comments && result.comments.length > 0 ? (
              <ul className="comment-list">
                {result.comments.map((c) => (
                  <li key={c.id} className="comment-item">
                    <p className="comment-content">{c.content}</p>
                    <p className="text-muted">{fmtDateTime(c.created_at)}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">Chưa có phản hồi công khai nào.</p>
            )}
          </div>
        )}

        <p className="portal-foot">
          <Link to="/">← Gửi yêu cầu mới</Link> · <Link to="/login">Nhân viên? Đăng nhập</Link>
        </p>
      </section>
    </div>
  );
}

function labelOfStatus(s) {
  return ({ OPEN: 'Mở', IN_PROGRESS: 'Đang xử lý', PENDING: 'Chờ bổ sung thông tin', RESOLVED: 'Đã giải quyết', CLOSED: 'Đã đóng' })[s] || s;
}
```

> Note: `labelOfStatus` is duplicated in Steps 3–4 intentionally (writing-plans: repeat code rather than "similar to X") — it is trivial. If you prefer, import from `labels.js` instead and delete both local copies; that is an acceptable improvement. `created.requester_name` is **not** returned by `PortalTicketOut` (Task 4 returns only code/status/subject/created_at), so the success copy in Step 3 reads "Cảm ơn bạn" — do not reference a `requester_name` that does not exist on the response.

- [ ] **Step 5: Create the portal stylesheet**

Create `frontend/src/styles/portal.css` (vanilla CSS over `tokens.css`; light/dark handled by the tokens):

```css
/* S2 Public Portal (design spec 6.3: vanilla CSS, token-driven). */
.portal-page { min-height: 100vh; background: var(--color-surface); display: flex; align-items: flex-start; justify-content: center; padding: var(--space-8) var(--space-4); }
.portal-card { width: 100%; max-width: 640px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-8); box-shadow: var(--shadow-sm); display: flex; flex-direction: column; gap: var(--space-4); }
.portal-card h1 { margin: 0; font-size: var(--font-size-lg); }
.portal-card form { display: flex; flex-direction: column; gap: var(--space-4); }
.portal-code { font-size: 1.5rem; font-weight: 700; letter-spacing: 0.04em; text-align: center; padding: var(--space-4); border: 1px dashed var(--color-primary); border-radius: var(--radius-md); color: var(--color-primary); background: var(--color-surface); }
.portal-actions { display: flex; gap: var(--space-3); justify-content: center; }
.btn-ghost { padding: var(--space-2) var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-sm); color: var(--color-text); text-decoration: none; text-align: center; }
.btn-ghost:hover { background: var(--color-surface); }
.portal-foot { margin: 0; font-size: var(--font-size-sm); color: var(--color-text-muted); }
.track-result { border-top: 1px solid var(--color-border); padding-top: var(--space-4); display: flex; flex-direction: column; gap: var(--space-3); }
.track-meta { display: grid; grid-template-columns: max-content 1fr; gap: var(--space-2) var(--space-4); margin: 0; font-size: var(--font-size-sm); }
.track-meta dt { color: var(--color-text-muted); }
.track-meta dd { margin: 0; font-weight: 500; }
.comment-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
.comment-item { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); background: var(--color-surface); }
.comment-content { margin: 0 0 var(--space-1); white-space: pre-wrap; }
.portal-card .field span { display: block; margin-bottom: var(--space-1); }
/* field/btn/form-error reused with S1 auth.css definitions; keep in sync. */
.field { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm); }
.field input, .field select, .field textarea { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text); font-size: var(--font-size-base); font-family: inherit; }
.field input:focus, .field select:focus, .field textarea:focus { outline: 2px solid var(--color-primary); outline-offset: 1px; border-color: transparent; }
.btn-primary { padding: var(--space-2) var(--space-4); background: var(--color-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: var(--font-size-base); cursor: pointer; text-decoration: none; text-align: center; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.form-error { color: var(--color-danger); margin: 0; font-size: var(--font-size-sm); }
.text-muted { color: var(--color-text-muted); }
```

> Note: `.field`, `.btn-primary`, `.form-error`, `.text-muted` are re-declared (identical to the auth.css subset) so the **public** portal never depends on the S1 stylesheet being loaded — the portal pages must render standalone. Both files must keep the same rule bodies; if you refactor to a shared utility sheet, that is fine, but the visual result must not change.

- [ ] **Step 6: Reroute `/` → portal, add `/track`, move health to `/health`**

Edit `frontend/src/App.jsx`:

```jsx
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, RequireRoles } from './auth/guards.jsx';
import { AdminLanding, AgentLanding, ManagerLanding, RoleLandingRedirect } from './app/Landings.jsx';
import AppShell from './app/AppShell.jsx';
import PortalCreatePage from './pages/PortalCreatePage.jsx';
import PortalTrackPage from './pages/PortalTrackPage.jsx';
import HealthPage from './pages/HealthPage.jsx';
import LoginPage from './pages/LoginPage.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PortalCreatePage />} />
        <Route path="/track" element={<PortalTrackPage />} />
        <Route path="/health" element={<HealthPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<RoleLandingRedirect />} />
          <Route
            path="tickets"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <AgentLanding />
              </RequireRoles>
            }
          />
          <Route
            path="dashboard"
            element={
              <RequireRoles roles={['MANAGER', 'ADMIN']}>
                <ManagerLanding />
              </RequireRoles>
            }
          />
          <Route
            path="admin"
            element={
              <RequireRoles roles={['ADMIN']}>
                <AdminLanding />
              </RequireRoles>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

> The `/app/tickets` placeholder stays for this task (Task 6 replaces it). `AgentLanding` is still imported — do not delete the import until Task 6 removes the placeholder route. HealthPage keeps its own `/api/health/*` fetches; only its route moves.

- [ ] **Step 7: Build to verify no syntax/import errors**

Run: `cd "D:/DuAm/HeThongHoTroAI/frontend" && npm run build`
Expected: Vite build succeeds ("built in …" with no error). Fix any import/JSX errors before committing.

- [ ] **Step 8: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add frontend/src/api/client.js frontend/src/lib/labels.js frontend/src/pages/PortalCreatePage.jsx frontend/src/pages/PortalTrackPage.jsx frontend/src/styles/portal.css frontend/src/App.jsx
git commit -m "feat(frontend): S2 public portal (create + track) with multipart client, labels, /health route

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Internal Tickets list + detail pages (status, assign, comments, attachments)

**Why one task:** this is the staff surface of S2 (design spec §6.2 rows `/app/tickets` and `/app/tickets/:id`). It replaces the S1 `AgentLanding` placeholder on the `tickets` route and wires the Task 4 staff endpoints (list/detail/status/assign/comments/attachments/download/teams) into a working list → detail flow, so the §10 demo — "khách gửi → manager gán → agent thấy → bình luận → RESOLVED" — is clickable in the browser. Controller decisions 1, 2, 7, 8 shape the UI: the Assign dialog is MANAGER/ADMIN only; status advance is explicit; the detail page is the single read surface (no separate comments/history routes).

**Files:**
- Create: `frontend/src/pages/TicketsListPage.jsx`
- Create: `frontend/src/pages/TicketDetailPage.jsx`
- Create: `frontend/src/styles/tickets.css`
- Modify: `frontend/src/App.jsx` (tickets routes; drop `AgentLanding` import)

**Interfaces:**
- Consumes (Task 4 exact shapes):
  - `GET /api/tickets?page&page_size&status&q&assigned_to_me` → `TicketListResponse{items:[TicketListItem],total,page,page_size}`; item fields `id,ticket_code,subject,category,priority,status,requester_name,requester_email,team_id,assigned_to,first_response_due_at,resolution_due_at,created_at,updated_at,version`.
  - `GET /api/tickets/{id}` → `TicketDetail` (all above + `sla_policy_id,first_response_at,resolved_at,closed_at` and arrays `comments:[CommentOut]` (`id,author_id,author_name,content,visibility,source,created_at,edited_at`), `attachments:[AttachmentOut]` (`id,original_name,mime_type,size_bytes,created_at,uploaded_by`), `history:[HistoryOut]` (`id,event_type,field_name,old_value,new_value,changed_by,reason,created_at`)).
  - `POST /api/tickets/{id}/status` JSON `{status,reason?,version}` → `TicketDetail` (fresh version).
  - `PATCH /api/tickets/{id}` JSON `{subject?|description?|category?|priority?,reason?,version}` → `TicketDetail`.
  - `POST /api/tickets/{id}/assign` JSON `{team_id,assigned_to|None,reason?,version}` → `TicketDetail` (MANAGER/ADMIN).
  - `POST /api/tickets/{id}/comments` multipart `content`,`visibility`,`files?` → `TicketDetail`.
  - `GET /api/teams` → `[TeamOut{id,name,members:[{id,full_name,team_role}]}]` (MANAGER/ADMIN).
  - `GET /api/attachments/{id}/download` → file bytes (via `api.fetchBlob`).
  - Errors: 404 `TICKET_NOT_FOUND`, 409 `VERSION_CONFLICT`, 400 `INVALID_STATUS_TRANSITION` / `ASSIGNEE_NOT_IN_TEAM`, 403 `ACCESS_DENIED`.
- Consumes (Task 5): `api.get/post/postForm/fetchBlob`, `triggerDownload`, `labels.js` (`STATUS_LABELS, PRIORITY_LABELS, CATEGORY_LABELS, VISIBILITY_LABELS, labelOf, fmtDateTime`).
- Consumes (S1): `useAuth` (for `user.role` — assign visibility), `RequireRoles` in App.jsx.
- Produces: routes `/app/tickets` (list) + `/app/tickets/:id` (detail), both AGENT/MANAGER/ADMIN.

- [ ] **Step 1: Build the Tickets list page**

Create `frontend/src/pages/TicketsListPage.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client.js';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/tickets.css';

const PAGE_SIZE = 10;

export default function TicketsListPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);          // TicketListItem[]
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [status, setStatus] = useState('');      // '' = all
  const [q, setQ] = useState('');
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [submittedQ, setSubmittedQ] = useState('');

  async function load(nextPage = page, filters = {}) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(PAGE_SIZE),
      });
      const st = filters.status ?? status;
      const query = filters.q ?? submittedQ;
      const mine = filters.assignedToMe ?? assignedToMe;
      if (st) params.set('status', st);
      if (query) params.set('q', query);
      if (mine) params.set('assigned_to_me', 'true');
      const body = await api.get(`/api/tickets?${params.toString()}`);
      setRows(body.items);
      setTotal(body.total);
      setPage(nextPage);
    } catch (err) {
      setError(err.message || 'Không thể tải danh sách vé.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(1, { status, q: submittedQ, assignedToMe });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, submittedQ, assignedToMe]);

  function applySearch(e) {
    e.preventDefault();
    setSubmittedQ(q.trim());
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="page tickets-page">
      <div className="page-head">
        <h1>Vé hỗ trợ</h1>
        <p className="text-muted">Danh sách vé trong phạm vi của bạn.</p>
      </div>

      <form className="tickets-filters" onSubmit={applySearch}>
        <input
          className="filter-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={100}
          placeholder="Tìm theo mã hoặc nội dung…"
          aria-label="Tìm kiếm"
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Lọc theo trạng thái">
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <label className="filter-check">
          <input type="checkbox" checked={assignedToMe} onChange={(e) => setAssignedToMe(e.target.checked)} />
          Vé của tôi
        </label>
        <button type="submit" className="btn-secondary">Tìm</button>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      {loading && <p className="text-muted">Đang tải…</p>}
      {!loading && !error && rows.length === 0 && (
        <div className="empty-state">
          <p>Không có vé nào khớp điều kiện lọc.</p>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <>
          <div className="table-scroll">
            <table className="tickets-table">
              <thead>
                <tr>
                  <th>Mã</th><th>Tiêu đề</th><th>Khách hàng</th>
                  <th>Phân loại</th><th>Ưu tiên</th><th>Trạng thái</th><th>Cập nhật</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id} className="tickets-row" onClick={() => navigate(`/app/tickets/${t.id}`)}>
                    <td className="code-cell">{t.ticket_code}</td>
                    <td className="subject-cell">{t.subject}</td>
                    <td>{t.requester_name}</td>
                    <td>{labelOf(CATEGORY_LABELS, t.category)}</td>
                    <td><span className={`badge badge--${(t.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, t.priority)}</span></td>
                    <td><span className={`badge badge--${(t.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, t.status)}</span></td>
                    <td>{fmtDateTime(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <button className="btn-secondary" disabled={page <= 1} onClick={() => load(page - 1)}>‹ Trước</button>
            <span className="text-muted">Trang {page} / {totalPages} ({total} vé)</span>
            <button className="btn-secondary" disabled={page >= totalPages} onClick={() => load(page + 1)}>Sau ›</button>
          </div>
        </>
      )}
    </section>
  );
}
```

> `Link` is imported but unused in the list page above (navigation is via `useNavigate`); remove `Link` from the import if you prefer, or keep it — the build only fails on missing modules, not unused imports.

- [ ] **Step 2: Build the Ticket detail page**

Create `frontend/src/pages/TicketDetailPage.jsx`. This is the largest FE file of the slice — read it end to end before editing. All four write actions (status, edit fields, assign, comment) send the ticket's **current `version`** from state and replace local state with the fresh `TicketDetail` returned (so `version` always stays in sync — Global Constraint: optimistic lock).

```jsx
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, triggerDownload } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import {
  CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS, VISIBILITY_LABELS,
  fmtDateTime, labelOf,
} from '../lib/labels.js';
import '../styles/tickets.css';

const MAX_FILES = 5;

// Mirror of backend state_machine.STATUS_FLOW (Task 1) — the UI only offers legal moves.
const NEXT_STATUSES = {
  OPEN: ['IN_PROGRESS', 'PENDING'],
  IN_PROGRESS: ['PENDING', 'RESOLVED'],
  PENDING: ['IN_PROGRESS'],
  RESOLVED: ['CLOSED', 'IN_PROGRESS'],
  CLOSED: ['IN_PROGRESS'],
};

function fmtBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(1)} KB`;
}

function eventText(h) {
  // changed_by is a user id (HistoryOut has no author_name); the audit log holds
  // the actor for S6 — the timeline shows the event + reason, not a raw id.
  switch (h.event_type) {
    case 'STATUS_CHANGED':
      return `Trạng thái: ${h.old_value || '—'} → ${h.new_value || '—'}`;
    case 'ASSIGNED':
      return 'Phân công được cập nhật';
    case 'COMMENT_ADDED':
      return 'Bình luận được thêm';
    case 'ATTACHMENT_ADDED':
      return 'Tệp đính kèm được thêm';
    case 'FIELD_UPDATED':
      return `Cập nhật ${h.field_name || 'trường'}: ${String(h.old_value ?? '—')} → ${String(h.new_value ?? '—')}`;
    default:
      return `${h.event_type}${h.field_name ? ` (${h.field_name})` : ''}`;
  }
}

export default function TicketDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const canAssign = user?.role === 'MANAGER' || user?.role === 'ADMIN';

  const [detail, setDetail] = useState(null); // TicketDetail | null
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // status dialog
  const [statusDialog, setStatusDialog] = useState(null); // target status | null
  const [statusReason, setStatusReason] = useState('');
  const [statusBusy, setStatusBusy] = useState(false);

  // edit dialog
  const [editOpen, setEditOpen] = useState(false);
  const [editReason, setEditReason] = useState('');
  const [editForm, setEditForm] = useState({ subject: '', description: '', category: '', priority: '' });
  const [editBusy, setEditBusy] = useState(false);

  // assign dialog
  const [assignOpen, setAssignOpen] = useState(false);
  const [teams, setTeams] = useState([]);
  const [teamId, setTeamId] = useState('');
  const [assigneeId, setAssigneeId] = useState('');
  const [assignReason, setAssignReason] = useState('');
  const [assignBusy, setAssignBusy] = useState(false);

  // comment composer
  const [content, setContent] = useState('');
  const [visibility, setVisibility] = useState('PUBLIC');
  const [files, setFiles] = useState([]);
  const [commentBusy, setCommentBusy] = useState(false);

  async function loadDetail() {
    setLoading(true);
    setLoadError(null);
    try {
      const body = await api.get(`/api/tickets/${id}`);
      setDetail(body);
      setEditForm({
        subject: body.subject, description: body.description,
        category: body.category, priority: body.priority,
      });
      setTeamId(body.team_id || '');
      setAssigneeId(body.assigned_to || '');
    } catch (err) {
      setLoadError(err.message || 'Không thể tải vé.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ---- status change -------------------------------------------------------
  const submitStatus = useCallback(async () => {
    const reopen = (detail?.status === 'RESOLVED' || detail?.status === 'CLOSED') && statusDialog === 'IN_PROGRESS';
    if (reopen && !statusReason.trim()) {
      setActionError('Cần nhập lý do khi mở lại vé.');
      return;
    }
    setStatusBusy(true);
    setActionError(null);
    try {
      const body = await api.post(`/api/tickets/${id}/status`, {
        status: statusDialog,
        reason: statusReason.trim() || null,
        version: detail.version,
      });
      setDetail(body);
      setEditForm({ subject: body.subject, description: body.description, category: body.category, priority: body.priority });
      setStatusDialog(null);
      setStatusReason('');
    } catch (err) {
      handleActionError(err);
    } finally {
      setStatusBusy(false);
    }
  }, [detail, statusDialog, statusReason, id]);

  // ---- edit fields ----------------------------------------------------------
  const submitEdit = useCallback(async () => {
    setEditBusy(true);
    setActionError(null);
    try {
      const patch = { version: detail.version };
      for (const key of ['subject', 'description', 'category', 'priority']) {
        if (editForm[key] !== detail[key]) patch[key] = editForm[key];
      }
      if (editReason.trim()) patch.reason = editReason.trim();
      const body = await api.patch(`/api/tickets/${id}`, patch);
      setDetail(body);
      setEditOpen(false);
      setEditReason('');
      setEditForm({
        subject: body.subject, description: body.description,
        category: body.category, priority: body.priority,
      });
    } catch (err) {
      handleActionError(err);
    } finally {
      setEditBusy(false);
    }
  }, [detail, editForm, editReason, id]);

  // ---- assign ---------------------------------------------------------------
  const openAssign = useCallback(async () => {
    setActionError(null);
    if (teams.length === 0) {
      try {
        const body = await api.get('/api/teams');
        setTeams(body);
        const preferred = body.find((t) => String(t.id) === String(teamId)) || body[0];
        if (preferred) {
          setTeamId(String(preferred.id));
          setAssigneeId(detail?.assigned_to && preferred.members.some((m) => String(m.id) === String(detail.assigned_to))
            ? detail.assigned_to : '');
        }
      } catch (err) {
        setActionError(err.message || 'Không thể tải danh sách nhóm.');
        return;
      }
    }
    setAssignOpen(true);
  }, [teams, teamId, detail]);

  const submitAssign = useCallback(async () => {
    if (!teamId) { setActionError('Vui lòng chọn nhóm.'); return; }
    setAssignBusy(true);
    setActionError(null);
    try {
      const body = await api.post(`/api/tickets/${id}/assign`, {
        team_id: teamId,
        assigned_to: assigneeId || null,
        reason: assignReason.trim() || null,
        version: detail.version,
      });
      setDetail(body);
      setAssignOpen(false);
      setAssignReason('');
    } catch (err) {
      handleActionError(err);
    } finally {
      setAssignBusy(false);
    }
  }, [detail, teamId, assigneeId, assignReason, id]);

  // ---- comment --------------------------------------------------------------
  const submitComment = useCallback(async () => {
    if (!content.trim()) { setActionError('Vui lòng nhập nội dung bình luận.'); return; }
    if (files.length > MAX_FILES) { setActionError(`Mỗi bình luận tối đa ${MAX_FILES} tệp.`); return; }
    setCommentBusy(true);
    setActionError(null);
    try {
      const fd = new FormData();
      fd.append('content', content.trim());
      fd.append('visibility', visibility);
      files.forEach((f) => fd.append('files', f));
      const body = await api.postForm(`/api/tickets/${id}/comments`, fd);
      setDetail(body);
      setContent('');
      setFiles([]);
      setVisibility('PUBLIC');
    } catch (err) {
      handleActionError(err);
    } finally {
      setCommentBusy(false);
    }
  }, [id, content, visibility, files]);

  function handleActionError(err) {
    if (err.error_code === 'VERSION_CONFLICT' || err.status === 409) {
      setActionError('Vé đã được người khác cập nhật. Đã tải lại dữ liệu mới nhất — vui lòng thử lại.');
      loadDetail();
    } else if (err.status === 403) {
      setActionError('Bạn không có quyền thực hiện thao tác này.');
    } else if (err.error_code === 'INVALID_STATUS_TRANSITION') {
      setActionError('Không thể chuyển sang trạng thái này.');
    } else if (err.error_code === 'ASSIGNEE_NOT_IN_TEAM') {
      setActionError('Người được phân công không thuộc nhóm đã chọn.');
    } else {
      setActionError(err.message || 'Thao tác thất bại. Vui lòng thử lại.');
    }
  }

  async function download(att) {
    try {
      const blob = await api.fetchBlob(`/api/attachments/${att.id}/download`);
      triggerDownload(blob, att.original_name);
    } catch (err) {
      setActionError(err.message || 'Không thể tải tệp.');
    }
  }

  if (loading) return <section className="page"><p className="text-muted">Đang tải…</p></section>;
  if (loadError) {
    return (
      <section className="page">
        <p className="form-error" role="alert">{loadError}</p>
        <button className="btn-secondary" onClick={() => navigate('/app/tickets')}>← Quay lại danh sách</button>
      </section>
    );
  }

  const currentTeam = teams.find((t) => String(t.id) === String(teamId));

  return (
    <section className="page ticket-detail">
      <p className="back-link"><Link to="/app/tickets">← Danh sách vé</Link></p>

      <header className="ticket-head">
        <div className="ticket-title-row">
          <h1>{detail.subject}</h1>
          <span className="code-cell code-badge">{detail.ticket_code}</span>
        </div>
        <div className="badge-row">
          <span className={`badge badge--${(detail.status || '').toLowerCase()}`}>{labelOf(STATUS_LABELS, detail.status)}</span>
          <span className={`badge badge--${(detail.priority || '').toLowerCase()}`}>{labelOf(PRIORITY_LABELS, detail.priority)}</span>
          <span className="badge">{labelOf(CATEGORY_LABELS, detail.category)}</span>
        </div>
        <p className="text-muted">
          {detail.requester_name} · {detail.requester_email} · Gửi lúc {fmtDateTime(detail.created_at)}
        </p>
        {detail.resolution_due_at && (
          <p className="text-muted">Hạn xử lý: {fmtDateTime(detail.resolution_due_at)}</p>
        )}
      </header>

      {actionError && <p className="form-error" role="alert">{actionError}</p>}

      <div className="ticket-actions">
        <button className="btn-secondary" onClick={() => { setActionError(null); setEditOpen(true); }}>Chỉnh sửa</button>
        {canAssign && <button className="btn-secondary" onClick={openAssign}>Phân công</button>}
      </div>

      <div className="ticket-actions">
        <span className="text-muted">Đổi trạng thái:</span>
        {(NEXT_STATUSES[detail.status] || []).map((target) => (
          <button key={target} className="btn-secondary" type="button"
            onClick={() => { setActionError(null); setStatusReason(''); setStatusDialog(target); }}>
            {labelOf(STATUS_LABELS, target)}
          </button>
        ))}
      </div>

      <section className="ticket-description">
        <h2>Mô tả</h2>
        <p className="pre-wrap">{detail.description}</p>
      </section>

      <section className="composer">
        <h2>Phản hồi</h2>
        <label className="field">
          <span>Loại phản hồi</span>
          <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
            <option value="PUBLIC">Công khai (khách hàng xem được khi tra cứu)</option>
            <option value="INTERNAL">Nội bộ (chỉ nhân viên)</option>
          </select>
        </label>
        <textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Nhập nội dung phản hồi…" />
        <label className="field">
          <span>Tệp đính kèm (tối đa {MAX_FILES})</span>
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.txt,.docx"
            onChange={(e) => setFiles([...e.target.files])} />
        </label>
        <button className="btn-primary" disabled={commentBusy} onClick={submitComment}>
          {commentBusy ? 'Đang gửi…' : 'Gửi phản hồi'}
        </button>
      </section>

      <section className="timeline">
        <h2>Hoạt động</h2>
        <ul className="timeline-list">
          {detail.history.map((h) => (
            <li key={`h-${h.id}`} className="timeline-item timeline-event">
              <span className="event-text">{eventText(h)}</span>
              <span className="text-muted">{fmtDateTime(h.created_at)}</span>
              {h.reason && <p className="text-muted">Lý do: {h.reason}</p>}
            </li>
          ))}
          {detail.comments.map((c) => (
            <li key={`c-${c.id}`} className="timeline-item timeline-comment">
              <div className="comment-meta">
                <strong>{c.author_name || '—'}</strong>
                <span className={`badge badge--${(c.visibility || '').toLowerCase()}`}>{labelOf(VISIBILITY_LABELS, c.visibility)}</span>
                <span className="text-muted">{fmtDateTime(c.created_at)}</span>
              </div>
              <p className="pre-wrap">{c.content}</p>
            </li>
          ))}
          {detail.attachments.filter((a) => !a.comment).map((a) => (
            <li key={`a-${a.id}`} className="timeline-item timeline-attachment">
              <button className="linklike" onClick={() => download(a)}>📎 {a.original_name}</button>
              <span className="text-muted">{fmtBytes(a.size_bytes)}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Status change dialog */}
      {statusDialog && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Đổi trạng thái">
          <div className="modal">
            <h2>Đổi trạng thái thành {labelOf(STATUS_LABELS, statusDialog)}?</h2>
            <p className="text-muted">Mã {detail.ticket_code} — trạng thái hiện tại: {labelOf(STATUS_LABELS, detail.status)}</p>
            <label className="field">
              <span>Lý do {(detail.status === 'RESOLVED' || detail.status === 'CLOSED') && statusDialog === 'IN_PROGRESS' ? '(bắt buộc khi mở lại)' : '(không bắt buộc)'}</span>
              <textarea rows={3} value={statusReason} onChange={(e) => setStatusReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setStatusDialog(null)} disabled={statusBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitStatus} disabled={statusBusy}>
                {statusBusy ? 'Đang lưu…' : 'Xác nhận đổi trạng thái'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit dialog */}
      {editOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Chỉnh sửa vé">
          <div className="modal">
            <h2>Chỉnh sửa vé</h2>
            <label className="field"><span>Tiêu đề</span>
              <input value={editForm.subject} maxLength={200}
                onChange={(e) => setEditForm((f) => ({ ...f, subject: e.target.value }))} />
            </label>
            <label className="field"><span>Mô tả</span>
              <textarea rows={4} value={editForm.description} maxLength={20000}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
            </label>
            <label className="field"><span>Phân loại</span>
              <select value={editForm.category}
                onChange={(e) => setEditForm((f) => ({ ...f, category: e.target.value }))}>
                {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Ưu tiên</span>
              <select value={editForm.priority}
                onChange={(e) => setEditForm((f) => ({ ...f, priority: e.target.value }))}>
                {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Lý do thay đổi</span>
              <input value={editReason} maxLength={500} onChange={(e) => setEditReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setEditOpen(false)} disabled={editBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitEdit} disabled={editBusy}>
                {editBusy ? 'Đang lưu…' : 'Lưu thay đổi'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assign dialog */}
      {assignOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Phân công vé">
          <div className="modal">
            <h2>Phân công vé</h2>
            <label className="field"><span>Nhóm xử lý</span>
              <select value={teamId} onChange={(e) => { setTeamId(e.target.value); setAssigneeId(''); }}>
                <option value="">— Chọn nhóm —</option>
                {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select>
            </label>
            <label className="field"><span>Người phụ trách (để trống nếu chỉ gán nhóm)</span>
              <select value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
                <option value="">— Chưa phân công —</option>
                {(currentTeam?.members || []).map((m) => (
                  <option key={m.id} value={String(m.id)}>{m.full_name} ({m.team_role})</option>
                ))}
              </select>
            </label>
            <label className="field"><span>Lý do phân công</span>
              <input value={assignReason} maxLength={500} onChange={(e) => setAssignReason(e.target.value)} />
            </label>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setAssignOpen(false)} disabled={assignBusy}>Hủy</button>
              <button className="btn-primary" onClick={submitAssign} disabled={assignBusy}>
                {assignBusy ? 'Đang lưu…' : 'Xác nhận phân công'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
```

> Note: the "activity" timeline renders `history`, then `comments`, then top-level `attachments` (those without a `comment` field). Attachment rows returned by `TicketDetail` do **not** include a `comment` field (Task 4 `AttachmentOut` has no `comment_id`), so the filter `!a.comment` keeps all of them in the attachments section — comment-carried files are already visible inside their `history`/`comment` context. If a reviewer flags the `.filter((a) => !a.comment)` as dead logic, it is a harmless guard for a future S4 shape — keep it or drop it, your call, but never render the same attachment twice.

- [ ] **Step 3: Add `api.patch` to the client**

Edit `frontend/src/api/client.js` (Task 5 left the client with only `get/post/postForm`):

```js
export const api = {
  get: (path) => request(path),
  post: (path, data) => request(path, { method: 'POST', body: JSON.stringify(data ?? {}) }),
  // multipart: rawFetch already skips the JSON Content-Type for FormData (S2 portal upload).
  postForm: (path, formData) => request(path, { method: 'POST', body: formData }),
  // Binary GET (file download) with the same in-memory Bearer token as the JSON calls.
  fetchBlob: (path) => fetchBlob(path),
  patch: (path, data) => request(path, { method: 'PATCH', body: JSON.stringify(data ?? {}) }),
};
```

> Without this method the detail page's "Lưu thay đổi" cannot reach `PATCH /api/tickets/{id}`. Do not skip Step 3.

- [ ] **Step 4: Create the tickets stylesheet**

Create `frontend/src/styles/tickets.css`:

```css
/* S2 internal ticket list + detail (design spec 6.3: vanilla, token-driven). */
.tickets-page .page-head { display: flex; align-items: baseline; gap: var(--space-4); }
.tickets-page h1 { margin: 0; font-size: var(--font-size-lg); }
.tickets-filters { display: flex; flex-wrap: wrap; gap: var(--space-3); align-items: center; margin: var(--space-4) 0; }
.filter-input, .tickets-filters select { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text); }
.filter-check { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); }
.table-scroll { overflow-x: auto; }
.tickets-table { width: 100%; border-collapse: collapse; font-size: var(--font-size-sm); }
.tickets-table th, .tickets-table td { text-align: left; padding: var(--space-3); border-bottom: 1px solid var(--color-border); vertical-align: top; }
.tickets-table th { color: var(--color-text-muted); font-weight: 500; white-space: nowrap; }
.tickets-row { cursor: pointer; }
.tickets-row:hover { background: var(--color-surface); }
.code-cell { font-family: ui-monospace, 'Cascadia Code', Consolas, monospace; white-space: nowrap; }
.subject-cell { max-width: 340px; }
.pagination { display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-4); }
.badge-row { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.badge { display: inline-block; padding: 1px var(--space-2); border-radius: 999px; border: 1px solid var(--color-border); font-size: var(--font-size-sm); background: var(--color-surface); color: var(--color-text); }
.badge--open { background: #eef2ff; color: #3730a3; border-color: #c7d2fe; }
.badge--in_progress { background: #ecfeff; color: #155e75; border-color: #a5f3fc; }
.badge--pending { background: #fffbeb; color: #92400e; border-color: #fde68a; }
.badge--resolved { background: #f0fdf4; color: #166534; border-color: #bbf7d0; }
.badge--closed { background: #f3f4f6; color: #374151; border-color: #d1d5db; }
.badge--low { background: #f0fdf4; color: #166534; }
.badge--medium { background: #fffbeb; color: #92400e; }
.badge--high { background: #fff7ed; color: #9a3412; }
.badge--urgent { background: #fef2f2; color: #991b1b; }
.badge--public { background: #eff6ff; color: #1e40af; }
.badge--internal { background: #f5f3ff; color: #5b21b6; }
.btn-secondary { padding: var(--space-2) var(--space-3); background: var(--color-bg); color: var(--color-text); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: var(--font-size-base); cursor: pointer; }
.btn-secondary:hover:not(:disabled) { background: var(--color-surface); }
.btn-secondary:disabled { opacity: 0.6; cursor: not-allowed; }
.empty-state { padding: var(--space-8); text-align: center; color: var(--color-text-muted); border: 1px dashed var(--color-border); border-radius: var(--radius-md); }
/* detail */
.ticket-detail { max-width: 960px; }
.ticket-title-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.ticket-title-row h1 { margin: 0; font-size: var(--font-size-lg); }
.code-badge { border: 1px dashed var(--color-border); padding: 2px var(--space-2); border-radius: var(--radius-sm); }
.ticket-actions { display: flex; gap: var(--space-3); margin: var(--space-4) 0; }
.ticket-description, .composer, .timeline { margin: var(--space-6) 0 0; border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4) var(--space-6); background: var(--color-bg); }
.ticket-description h2, .composer h2, .timeline h2 { margin: 0 0 var(--space-3); font-size: var(--font-size-base); }
.pre-wrap { white-space: pre-wrap; }
.composer { display: flex; flex-direction: column; gap: var(--space-3); }
.composer textarea { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text); font-family: inherit; }
.timeline-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
.timeline-item { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); background: var(--color-surface); font-size: var(--font-size-sm); }
.timeline-event { display: flex; flex-direction: column; gap: var(--space-1); }
.comment-meta { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.comment-meta p { margin: var(--space-2) 0 0; }
.linklike { background: none; border: none; padding: 0; color: var(--color-primary); cursor: pointer; font-size: var(--font-size-sm); }
.linklike:hover { text-decoration: underline; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.5); display: flex; align-items: flex-start; justify-content: center; padding: var(--space-8) var(--space-4); z-index: 20; }
.modal { width: 100%; max-width: 520px; background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-6); display: flex; flex-direction: column; gap: var(--space-4); }
.modal h2 { margin: 0; font-size: var(--font-size-lg); }
.modal-actions { display: flex; justify-content: flex-end; gap: var(--space-3); }
.field { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--font-size-sm); }
.field input, .field select, .field textarea { padding: var(--space-2) var(--space-3); border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); color: var(--color-text); font-size: var(--font-size-base); font-family: inherit; }
.field input:focus, .field select:focus, .field textarea:focus { outline: 2px solid var(--color-primary); outline-offset: 1px; border-color: transparent; }
.form-error { color: var(--color-danger); margin: 0; font-size: var(--font-size-sm); }
.text-muted { color: var(--color-text-muted); }
.btn-primary { padding: var(--space-2) var(--space-4); background: var(--color-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: var(--font-size-base); cursor: pointer; }
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
```

> `.field`, `.btn-primary`, `.form-error`, `.text-muted` are re-declared identically again (same reason as Task 5 Step 5: the staff pages must not depend on which stylesheet happened to load). Note the dark-mode token swap is automatic via `tokens.css` `prefers-color-scheme`; the `badge--*` colours above are chosen for light mode — acceptable for S2 (a full accessibility/theming sweep is S7), but do not ship pure-red/green status text.

- [ ] **Step 5: Wire the routes in App.jsx**

Edit `frontend/src/App.jsx` — replace the tickets placeholder route and the `AgentLanding` import:

```jsx
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, RequireRoles } from './auth/guards.jsx';
import { AdminLanding, ManagerLanding, RoleLandingRedirect } from './app/Landings.jsx';
import AppShell from './app/AppShell.jsx';
import PortalCreatePage from './pages/PortalCreatePage.jsx';
import PortalTrackPage from './pages/PortalTrackPage.jsx';
import HealthPage from './pages/HealthPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import TicketsListPage from './pages/TicketsListPage.jsx';
import TicketDetailPage from './pages/TicketDetailPage.jsx';
```

and inside the `/app` route group replace the single `tickets` route with two routes:

```jsx
          <Route
            path="tickets"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <TicketsListPage />
              </RequireRoles>
            }
          />
          <Route
            path="tickets/:id"
            element={
              <RequireRoles roles={['AGENT', 'MANAGER', 'ADMIN']}>
                <TicketDetailPage />
              </RequireRoles>
            }
          />
```

> The `/app/dashboard` and `/app/admin` routes stay exactly as-is; `AgentLanding` in `Landings.jsx` becomes an unused export — leave the file alone (removing it is optional, not required; the build does not fail on unused exports).

- [ ] **Step 6: Build + manual smoke**

Build: `cd "D:/DuAm/HeThongHoTroAI/frontend" && npm run build`
Expected: Vite build succeeds. Fix JSX/import errors (the most likely: a missing `api.patch` because Step 3 was skipped, or a stray `AgentLanding` import).

Manual smoke against the running stack (backend :8001 already has the Task 4 routes via code-mount, or the container was rebuilt at acceptance — if the running backend predates Task 4, restart it first):
- Log in as a seeded agent (S1 creds) → land on `/app/tickets` → the list renders seeded `TK-DEMO*` tickets (agent scope = member teams + assigned).
- Open a ticket → status dialog advances OPEN→IN_PROGRESS (reason optional) and RESOLVED→CLOSED; reopening asks for a reason.
- Add a PUBLIC comment → detail stays on the fresh version; a track-page lookup of the same ticket (public, different browser/incognito) shows that comment.
- MANAGER/ADMIN sees "Phân công"; pick a team + an active member → save → detail shows team/assignee.

- [ ] **Step 7: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add frontend/src/api/client.js frontend/src/pages/TicketsListPage.jsx frontend/src/pages/TicketDetailPage.jsx frontend/src/styles/tickets.css frontend/src/App.jsx
git commit -m "feat(frontend): S2 staff ticket list + detail (status/edit/assign/comments/attachments)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Acceptance over the running stack + repo hygiene (.gitignore, README)

**Why one task:** closes the slice with the same acceptance gates S1 used — clean migration diff, all unit + integration suites green, then a live HTTP smoke that walks the §10 S2 demo end to end over the running compose stack (public portal create → manager assign → agent sees → comment → RESOLVED). It also stops the repo from accumulating uploaded demo files (`.gitignore` `backend/uploads/`) and documents the slice in the README so a reviewer/partner can replay it.

**Files:**
- Modify: `.gitignore` (add `backend/uploads/`)
- Modify: `README.md` (add `### S2 — Public Portal & Ticket core` block after the S1 block)
- No code files change in this task.

**Interfaces:** consumes every earlier task's code + tests; consumes the running demo stack (db :5433 / backend :8001 / frontend :8080 — if the backend is exposed on another host port, substitute it via `docker compose port backend 8000`).

- [ ] **Step 1: Confirm the working tree has no stray files**

Run: `cd "D:/DuAm/HeThongHoTroAI" && git status --short`
Expected: clean (only the planned commits from Tasks 1–6 on top of S1 HEAD `df78379`). If S1 integration leftovers exist, stash/remove before acceptance.

- [ ] **Step 2: Rebuild the demo containers so S2 is live**

The running backend image predates the `slowapi` dependency and the S2 routers/frontend build, so rebuild both (db untouched):

Run: `cd "D:/DuAm/HeThongHoTroAI" && docker compose up -d --build backend frontend`
Expected: `db` untouched/healthy; `backend` + `frontend` recreated. Wait for readiness (seed + alembic upgrade run inside the container on boot, idempotent):
Run: `powershell -Command "1..60 | ForEach-Object { try { $r = Invoke-RestMethod http://localhost:8001/api/health/ready; if ($r.status -eq 'ok') { 'READY'; break } } catch {}; Start-Sleep -Milliseconds 1000 }"`
Expected: prints `READY`. Then confirm no migration drift (runs against the compose DB through the backend container):
Run: `docker compose exec backend alembic check`
Expected: `No new upgrade operations detected.` (Global Constraint: no Alembic migration in S2).

- [ ] **Step 3: Run the unit suite**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: **58 passed** (S1 35 + Task 1–2 pure helpers/storage/rate-limit). No DB required.

- [ ] **Step 4: Run the integration suites (compose DB on :5433)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q`
Expected: all integration tests pass — S1 `test_auth.py` (unchanged), Task 3 `test_ticket_service.py` (service-level org-isolated flows), Task 4 `test_http_tickets.py` (HTTP flows incl. public create/track + assign + 404 anti-leak + download scope). Each test removes exactly what it created; the seeded demo rows remain untouched (verified in Task 3 — every delete is id-scoped).

- [ ] **Step 5: Live HTTP smoke — the §10 S2 demo end to end**

Walk the demo against the running backend (:8001). Uses the seeded demo identities from the README (hung.manager manages **Team Kỹ thuật**, which contains lan.agent). PowerShell `curl.exe` + `jq` are expected on the host; if `jq` is absent, read the raw JSON and copy ids manually.

5a. Public portal create (multipart):
```powershell
curl.exe -s -X POST http://localhost:8001/api/public/tickets `
  -F "requester_name=Khách Hàng Demo" `
  -F "requester_email=khach.s2demo@example.com" `
  -F "subject=Không đăng nhập được sau khi đổi mật khẩu" `
  -F "description=Đã đổi mật khẩu theo email hướng dẫn nhưng vẫn báo sai mật khẩu." `
  -F "category=ACCOUNT"
```
Expected: `201` with `{"ticket_code":"TK-XXXXXXXX","status":"OPEN","subject":...}`. Note the code.

5b. Manager login + assign to lan.agent:
```powershell
$MGR = (curl.exe -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" `
  -d '{"email":"hung.manager@example.com","password":"hung.manager@Dev123"}') | ConvertFrom-Json
$H = @{ Authorization = "Bearer $($MGR.access_token)" }
curl.exe -s http://localhost:8001/api/teams -H "Authorization: Bearer $($MGR.access_token)"
```
Expected: the response lists **Team Kỹ thuật** (hung manages it) with members incl. `Trần Thị Lan` (`team_role` MEMBER). Capture `teamId` and `lanId` from that payload. Then:
```powershell
$LIST = curl.exe -s "http://localhost:8001/api/tickets?q=TK-XXXXXXXX" -H "Authorization: Bearer $($MGR.access_token)"
# copy ticket id + its current version from the item
curl.exe -s -X POST "http://localhost:8001/api/tickets/{ticketId}/assign" `
  -H "Authorization: Bearer $($MGR.access_token)" -H "Content-Type: application/json" `
  -d "{\"team_id\":\"{teamId}\",\"assigned_to\":\"{lanId}\",\"version\":{version}}"
```
Expected: `200` and the response `team_id`/`assigned_to` populated. (Substitute the `{...}` placeholders with the values you captured — do not paste literal braces.)

5c. Agent sees the assigned ticket + advances to RESOLVED with a PUBLIC comment:
```powershell
$AGT = (curl.exe -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" `
  -d '{"email":"lan.agent@example.com","password":"lan.agent@Dev123"}') | ConvertFrom-Json
curl.exe -s "http://localhost:8001/api/tickets?assigned_to_me=true" -H "Authorization: Bearer $($AGT.access_token)"
curl.exe -s -X POST "http://localhost:8001/api/tickets/{ticketId}/comments" `
  -H "Authorization: Bearer $($AGT.access_token)" `
  -F "content=Chúng tôi đã đặt lại mật khẩu, bạn vui lòng thử lại nhé." -F "visibility=PUBLIC"
curl.exe -s -X POST "http://localhost:8001/api/tickets/{ticketId}/status" `
  -H "Authorization: Bearer $($AGT.access_token)" -H "Content-Type: application/json" `
  -d "{\"status\":\"RESOLVED\",\"version\":{newVersion}}"
```
Expected: the agent's `assigned_to_me` list contains the ticket; the comment returns a fresh detail whose `first_response_at` is stamped; the status transition returns `"status":"RESOLVED"`.

5d. Public track returns only the PUBLIC reply (anti-leak FR-PUB-06/07):
```powershell
curl.exe -s -X POST http://localhost:8001/api/public/track `
  -H "Content-Type: application/json" `
  -d '{"email":"khach.s2demo@example.com","ticket_code":"TK-XXXXXXXX"}'
```
Expected: `200` with the ticket + exactly the one PUBLIC comment above (no internal notes/assignment fields).

5e. Browser pass (optional but recommended): open http://localhost:8080 → public portal at `/`; create a ticket, then login as `lan.agent@example.com` → list shows it under `/app/tickets` → open detail → comment → RESOLVED. Also hit `/health` (the moved route) and confirm the old `/` now shows the portal, not health.

> The demo ticket created in Step 5a persists in the compose DB — that is intended demo data, not test residue (each pytest run is self-cleaning; this curl flow is the manual §10 demo).

- [ ] **Step 6: Add `backend/uploads/` to .gitignore**

Edit the repo root `.gitignore` — append (under the existing upload-related line if one exists, otherwise at the end):

```gitignore
# S2 uploaded attachments (stored under backend/uploads/, DB keeps metadata only)
backend/uploads/
```

Then confirm stored files are ignored:
Run: `cd "D:/DuAm/HeThongHoTroAI" && git check-ignore backend/uploads/ && git status --short`
Expected: `git check-ignore` prints the path; status shows no untracked `backend/uploads` files.

- [ ] **Step 7: Document the slice in the README**

Edit `README.md` — insert this block after the S1 block (after the line reading `Chi tiết kỹ thuật: docs/superpowers/plans/2026-09-02-s1-auth-rbac.md.`):

```markdown
### S2 — Public Portal & Ticket core

Từ S2, khách hàng **không cần đăng nhập** để gửi yêu cầu hỗ trợ và tra cứu tiến độ:

- **`/`** — Biểu mẫu gửi yêu cầu (họ tên, email, tiêu đề, mô tả, phân loại, tệp đính kèm tối đa 5 tệp). Vé được tạo ở trạng thái `OPEN`, ưu tiên `MEDIUM`, kèm hạn SLA.
- **`/track`** — Tra cứu bằng mã vé + email. Chỉ hiển thị thông tin công khai (không lộ ghi chú nội bộ, phân công hay audit). Nhập sai mã/email trả về cùng một thông báo (chống dò vé).
- **`/app/tickets`** và **`/app/tickets/:id`** — Nhân viên/quản lý/admin: danh sách có lọc (trạng thái, tìm kiếm, "vé của tôi"), chi tiết vé với dòng thời gian (phản hồi, lịch sử, tệp), đổi trạng thái theo state machine, bình luận công khai/nội bộ, đính kèm + tải tệp.
- **Phân công tối thiểu** (S2): Quản lý/Admin gán vé vào nhóm + người phụ trách. Quản lý chỉ gán được vào nhóm mình quản lý; người được gán phải thuộc nhóm và còn hoạt động.
- Truy cập theo scope: Admin xem tất cả; Quản lý xem vé nhóm mình quản lý + vé chưa gán nhóm; Nhân viên xem vé nhóm mình + vé được gán cho mình. Vé ngoài scope trả về `404` (không lộ thông tin).
- Mọi thao tác ghi đều dùng **optimistic lock**: body kèm `version`; ghi sai phiên bản trả về `409 VERSION_CONFLICT`.

Demo nhanh: gửi vé tại `/` → đăng nhập `lan.agent@example.com` (mật khẩu seed ở bảng S1) → mở vé trong `/app/tickets` → phản hồi → chuyển `RESOLVED`. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s2-ticket-core.md`.
```

> Also update the S1 lead-in line 12 (`Health: http://localhost:8000/health/...`) only if it is inaccurate for this deployment — in this workspace the demo backend is on **:8001** and health moved to **`/health`** in S2. If you touch it, keep the wording generic (`http://localhost:{BACKEND_HOST_PORT}/health/...`) so the README stays correct for both the compose default and this overridden run.

- [ ] **Step 8: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add .gitignore README.md
git commit -m "docs(s2): acceptance gates green, ignore backend/uploads, README S2 demo block

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-review (writing-plans checklist, run by the plan author)

**1. Spec coverage.** Walked the design spec §10 S2 deliverable + SRS against the tasks:
- Public create w/ validation + code + SLA: Tasks 1 (code/SLA helpers), 2 (schemas), 3 (`create_portal_ticket`), 4 (router), 5 (form). ✔
- Public track + anti-leak 404 + rate limit: Tasks 1 (Settings/rates), 2 (`rate_limit.py`), 3 (`track_public`), 4 (router), 5 (page). ✔
- Upload allowlist/size/count + storage cleanup: Tasks 1 (`file_rules`), 2 (`storage`), 3 (service), 4 (`store_many` + rollback + HTTP tests). ✔
- Internal list (search/filter/paging + scoping), detail + history, field update w/ optimistic lock, state machine + reopen w/ reason, comments public/internal + `first_response_at`, notes, attachments w/ auth + download, history + audit: Task 3 (service) + Task 4 (routers/tests). ✔
- Frontend portal + list + detail (+ composer/dialogs): Tasks 5–6. ✔
- Explicit non-goals honored: full assign workflow (S3), staff ticket creation (S3), GET comments/history standalone (deferred in Controller 8), sort param on list (not in API), no migration. ✔
- SRS 10.2 codes used exactly; `ASSIGNEE_NOT_IN_TEAM` surfaced via router + FE message. ✔

**2. Placeholder scan.** Every step carries concrete code or a concrete run/expected. The three deliberate cross-checks left in the text are real (a `.gitignore` line for Task 3 cleanup, `api.patch` required for `submitEdit`, rebuild requirement in Task 7) — none is a "TBD". No `TODO`/`implement later` remains; the earlier draft stubs in Task 4/6 were replaced with final code. ✔

**3. Type/name consistency.** Spot-checked the seams between tasks:
- Schemas (`PortalCreateRequest`, `TicketDetail`, `CommentOut`, `AttachmentOut`, `HistoryOut`, `AssignRequest`, `TeamOut`) match the service + router mappers in Tasks 2–4, and the FE reads exactly those fields (Task 6 uses `detail.version`, `h.event_type`, `a.original_name`, `t.ticket_code`, etc.). ✔
- Route paths are uniform across the plan (`/api/public/tickets`, `/api/public/track`, `/api/tickets/{id}`, `/api/tickets/{id}/status`, `/api/tickets/{id}/assign`, `/api/tickets/{id}/comments`, `/api/attachments/{id}/download`, `/api/teams`). ✔
- Settings knobs added in Task 1 (Step 2) are consumed identically in Task 4 (`upload_dir`, `upload_max_files`, `max_upload_size_mb`, `allowed_file_types`, `public_create_rate`, `public_track_rate`, `rate_limit_enabled`). ✔
- `store_many` signature (Task 4 Step 1) is the one both routers call. ✔
- FE `labels.js` exports used by both portal (Task 5) and staff (Task 6) pages; `api.postForm/fetchBlob/triggerDownload/patch` added before use. ✔
- Unit-test counts stay monotonic (Task 1 → Task 2 → … → 58 in Task 4 Step 6 / Task 7 Step 3). ✔
- Demo identities in Task 7 match `seed.py`/README (hung.manager manages Team Kỹ thuật which contains lan.agent). ✔

No task-gating contradictions with the Global Constraints or the Controller decisions surfaced during authoring that were not already ratified above.

---

*Plan ends. Execution starts at Task 1 when the mode is chosen (Task 7 is the acceptance gate; do not reorder).*
