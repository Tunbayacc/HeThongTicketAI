# S5 — Dashboard & báo cáo (role-scoped KPIs · SLA · time-series trends) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the S5 slice of the AI-integrated customer-support system per design spec §10 S5 + SRS FR-REP-01/02/04/05/06/07/08/09/11 (UC-13): two staff dashboard endpoints (`/api/dashboard/summary`, `/api/dashboard/trends`) whose numbers are **role-scoped with exactly the same scope as the Ticket List** (FR-REP-11), plus a frontend `/app/dashboard` page (KPI cards, SLA buckets, avg times, hand-drawn SVG trends) for AGENT/MANAGER/ADMIN.

**Architecture:** Dashboard aggregation lives in a new `app/services/dashboard_service.py` that reuses a new **public** scope wrapper `build_ticket_scope_conditions(...)` added in `ticket_service.py` (same SQL conditions `list_tickets` uses — no duplicated/private-`_` imports across modules). Pure time/SLA math lives in `app/services/dashboard_logic.py` (unit-tested, no DB). A new `app/api/dashboard.py` router is registered at prefix `/api`. The FE replaces the existing `/app/dashboard` placeholder (`ManagerLanding`) with `DashboardPage` (date-range presets + custom dates, SVG charts, 2-theme via CSS tokens).

**Tech Stack:** FastAPI + SQLAlchemy async + asyncpg (existing) · React + Vite + hand-rolled `fetch` client + vanilla CSS tokens (existing) · Python stdlib `zoneinfo` (reporting TZ). No new runtime dependency, no new Alembic migration.

## Global Constraints (bind every task; reviewers use these as the attention lens)

- **Scope identity with Ticket List (FR-REP-11).** Dashboard scope is computed ONLY through `ticket_service.build_ticket_scope_conditions(session, *, user)` — a new public wrapper around the existing `_view_team_ids` + `_scope_conds` (`ticket_service.py:54-81`). Consumers never import `_`-private helpers. `list_tickets` is refactored to call the same wrapper so there is literally one definition. Out-of-scope rows are simply excluded from aggregates (counts, never 404).
- **Role audience = all staff.** AGENT · MANAGER · ADMIN reach `/api/dashboard/*` and the `/app/dashboard` page. Update `deps._FEATURE_SCOPES["dashboard"]` from `{"MANAGER","ADMIN"}` → `{"AGENT","MANAGER","ADMIN"}` (`deps.py:24-28`) and the FE route guard + nav.
- **Manager "no-team" rule is intentional and shared.** Manager scope keeps `Ticket.team_id.is_(None)` (the "chưa gán nhóm" common intake queue, `ticket_service.py:79-80`, Controller decision 2). It is kept **only** because Ticket List already uses it; a parity test locks dashboard = list. Dashboard must NEVER have a scope different from Ticket List.
- **Population & time window (user-approved semantics).** All numbers in a response describe one population: in-scope tickets with `created_at >= from_utc AND created_at < to_excl_utc`. The window is expressed by the FE as **two local dates** (start, end); the backend converts both day boundaries **in the reporting timezone (Asia/Ho_Chi_Minh)** to UTC instants: `from_utc = local_midnight(from)` , `to_excl_utc = local_midnight(to + 1 day)`. Add `Settings.reporting_timezone: str = "Asia/Ho_Chi_Minh"` (`config.py`). Defaults when params absent: `to = today`, `from = today − 29 days` (i.e. a rolling 30-day window), both in reporting TZ. `from > to` → `422 VALIDATION_ERROR`. A `to` in the future is clamped to today.
- **No "Tất cả" preset and no global 365-day clamp.** UI presets: **7 / 30 / 90 / 180 / 365** ngày, **default 30**; the FE also offers custom start/end date inputs. NFR-PER-06 bounds *performance at 12 months*, not the permitted range — do not reject wider ranges server-side.
- **SLA buckets (FR-REP-04).** Buckets are computed with the existing `deadline_state(due_at, now, sla_due_soon_minutes)` (`sla_service.py:14-22`) and the persisted `sla_due_soon_minutes = 120` (`config.py:50`). A ticket is **tracked** iff status ∈ {OPEN, IN_PROGRESS, PENDING} **and** it has a relevant unsatisfied deadline (see `sla_state()` in Task 2). ON_TIME / DUE_SOON / OVERDUE are **mutually exclusive** and `on_time + due_soon + overdue == tracked` by construction — an integration test asserts the invariant. Pause-on-pending: deadlines persisted on tickets are already pause-extended when leaving PENDING (`ticket_service.py:336-352`); while *currently* PENDING with `pause_on_pending=true` on the SLA policy, `sla_state()` adds the open pending duration to the effective deadline (mirrors the extension `change_status` will apply on exit). Seed policies all have `pause_on_pending=false`, so the paused path is dormant in the demo but unit-tested.
- **Averages (FR-REP-05).** `avg_first_response_seconds` = `avg(first_response_at − created_at)` over the population's tickets that already have `first_response_at` (first PUBLIC staff comment, `ticket_service.py:444-447`). `avg_resolution_seconds` = `avg(resolved_at − created_at)` over the population's tickets with `resolved_at` set. When no rows qualify the value is **`null`** — never `0` — and the FE renders "Chưa có dữ liệu". Computed averages are rounded to whole seconds with `int(round(value))` before returning.
- **Wire field naming (no Python identifier named `from`).** `RangeOut` uses `from_date` / `to_date` declared with `Field(alias="from")` / `Field(alias="to")` and `model_config = ConfigDict(populate_by_name=True)`; the router declares query params `from_date` / `to_date` via `Query(alias="from")` / `Query(alias="to")`. The JSON wire format stays `from` / `to`.
- **Validation envelope is the shared one.** A malformed date (FastAPI's native 422) is normalized by the existing `register_exception_handlers` (`app/core/errors.py`) — no Dashboard-specific error format. The inverted range maps our `ValueError` → `AppError(422, "VALIDATION_ERROR", "Khoảng thời gian không hợp lệ.")`. HTTP tests assert the exact envelope body.
- **Performance honesty (NFR-PER-06).** There is **no performance test yet** — NFR-PER-06 (P95 ≤ 5 s at 12 months) is **chưa xác nhận chính thức** in every gate and doc word. The live demo is only a functional smoke test and must never be cited as NFR evidence. The 365-day preset is still allowed; it is not a server-side cap.
- **Trends (user-approved semantics; aggregated in PostgreSQL).** Each trend bucket = number of tickets **created in that period**, split by their **current** status (a bucket's shape can change as tickets transition — the chart title must state "theo trạng thái hiện tại"). Granularity: **day** when the window span ≤ 62 days, else **month**. The DB does the counting with **`GROUP BY` status + day/month marker** (`date_trunc(gran, created_at AT TIME ZONE <reporting tz>)`); Python never loads the ticket set to count — it only normalizes and **fills**. The backend returns **one bucket per day/month of the resolved range, including empty buckets**, and every bucket always carries all 5 status keys (0-filled). The FE renders exactly what it receives — it never fabricates buckets/statuses — and shows an empty state when the window totals 0.
- **No unrelated changes.** The working-tree `GET /` experiment in `backend/app/main.py` was already **discarded** (no FE/test reference) — do not reintroduce it, and do not mix unrelated edits into S5 commits. Staff ticket creation stays OUT (S3/S4 scope note).
- **Error codes/envelope.** Reuse `AppError(status, code, message)`. New codes: date validation → `422 VALIDATION_ERROR`. Role guard → existing `403 ACCESS_DENIED` via `require_roles("AGENT","MANAGER","ADMIN")`.
- **Copy rules.** UI copy Vietnamese; enum/identifier values English. `STATUS_LABELS` / `PRIORITY_LABELS` reused (`frontend/src/lib/labels.js:3-16`).
- **Test env (unchanged S3/S4).** Unit = host venv `backend/.venv/Scripts/python -m pytest tests/unit -q`. Integration = `INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false` over the compose DB. Baseline suites: **unit 84** (81 + 3 S4 provider tests), **integration 47** (auth 3 + seed 1 + ticket_service 9 + http_tickets 10 + ai_service 14 + http_ai 10). S5 targets are reconciled at actuals in the Task 5 report (S3/S4 precedent — plan-prose counts are a guess; the final per-file table is authoritative).
- **Dispatch guardrails (carried from S3/S4).** Implementers run NO docker commands except the acceptance scope (`docker compose exec backend alembic check`, `docker compose ps`, `docker compose logs`, `docker compose restart backend`); work only on the files each brief lists; never modify seeded rows or `backend/app/db/seed.py`; never touch the foreign `hethongticketai` stack (:5432/:8000/:5173) or native postgres; never print `.env`/`JWT_SECRET_KEY`/`SEED_ADMIN_PASSWORD` or any API-key value. Demo stack (db :5433 / backend :8001 / frontend :8080) stays running. UI Vietnamese / identifiers English.

## File structure

Backend — new:
- `backend/app/services/dashboard_logic.py` — pure, DB-free: window resolution (reporting-TZ day boundaries → UTC), granularity pick, `bucket_labels()` (matches PG `to_char`), `sla_state()` classification.
- `backend/app/services/dashboard_service.py` — async aggregates over the DB using the scope wrapper; returns plain dicts.
- `backend/app/schemas/dashboard.py` — response models (Pydantic).
- `backend/app/api/dashboard.py` — `GET /dashboard/summary`, `GET /dashboard/trends`.
- `backend/tests/unit/test_dashboard_logic.py` — pure tests.
- `backend/tests/integration/test_dashboard.py` — service-level: direct parity with `list_tickets`, reference-SQL cross-check, real pause-on-pending policy test, SLA invariant, avg-null, trends full-window buckets.
- `backend/tests/integration/test_http_dashboard.py` — HTTP surface: RBAC, validation, shapes.

Backend — modified:
- `backend/app/services/ticket_service.py` — add public `build_ticket_scope_conditions()`; make `list_tickets` call it.
- `backend/app/core/config.py` — add `reporting_timezone: str = "Asia/Ho_Chi_Minh"`.
- `backend/app/core/deps.py` — `_FEATURE_SCOPES["dashboard"]` gains `"AGENT"`.
- `backend/app/main.py` — register `dashboard_router` at prefix `/api` (import + include).

Frontend — new:
- `frontend/src/pages/DashboardPage.jsx` — page + date-range toolbar + fetch.
- `frontend/src/components/DashboardTrendChart.jsx` — hand-drawn stacked SVG (no dependency).
- `frontend/src/styles/dashboard.css` — page styles (tokens only, 2 themes).

Frontend — modified:
- `frontend/src/App.jsx:45-52` — `/app/dashboard` guard roles → `['AGENT','MANAGER','ADMIN']`, element → `DashboardPage`.
- `frontend/src/app/AppShell.jsx:6-10` — NAV `{ to: '/app/dashboard', label: 'Bảng điều khiển', roles: ['AGENT','MANAGER','ADMIN'] }`.
- `frontend/src/app/Landings.jsx` — remove now-unrouted `ManagerLanding` (keep `AdminLanding` placeholder for S6).

Docs:
- `README.md` — add `### S5 — Dashboard & báo cáo` demo block after the S4 block.

## Interfaces produced (later tasks rely on these exact names)

- `ticket_service.build_ticket_scope_conditions(session, *, user) -> list[ColumnElement[bool]]` — public wrapper = `_scope_conds(user, await _view_team_ids(session, user))`; returns `[]` (ADMIN) or `[or_(...)]` (others).
- `dashboard_logic.resolve_window(from_date: date | None, to_date: date | None, *, now: datetime, tz_name: str, default_days: int = 30) -> tuple[datetime, datetime]` — returns `(utc_from, utc_to_excl)`; raises `ValueError` when `from_date > to_date`.
- `dashboard_logic.granularity_for(utc_from: datetime, utc_to_excl: datetime) -> str` — `"day"` when `(utc_to_excl - utc_from).days <= 62` else `"month"`.
- `dashboard_logic.bucket_labels(utc_from: datetime, utc_to_excl: datetime, *, tz_name: str, granularity: str) -> list[str]` — the contiguous list of day (`YYYY-MM-DD`) or month (`YYYY-MM`) labels spanning the resolved window in the reporting TZ. Labels use **calendar** year/month and MUST byte-match PostgreSQL `to_char(date_trunc(...), ...)` output (see Task 2), so the Python fill layer and the SQL `GROUP BY` labels agree.
- `dashboard_logic.sla_state(*, status: str, first_response_at, first_response_due_at, resolution_due_at, pause_on_pending: bool, pending_since, now: datetime, due_soon_minutes: int) -> str | None` — returns `"ON_TIME" | "DUE_SOON" | "OVERDUE" | None` (None = not SLA-tracked). Task 2 gives the exact algorithm.
- `dashboard_service.summary(session, *, user, from_date, to_date) -> dict` and `dashboard_service.trends(session, *, user, from_date, to_date) -> dict` — see response shapes below.
- Router paths (staff `AGENT/MANAGER/ADMIN`, registered at prefix `/api`, no rate limit): `GET /api/dashboard/summary`, `GET /api/dashboard/trends`, each with optional `from` / `to` query params (`YYYY-MM-DD`).

### Response shapes (verbatim contract)

`GET /api/dashboard/summary?from=2026-08-05&to=2026-09-03` → `200`:
```json
{
  "range": { "from": "2026-08-05", "to": "2026-09-03", "timezone": "Asia/Ho_Chi_Minh", "granularity": "day" },
  "kpi": {
    "total": 42,
    "by_status": { "OPEN": 10, "IN_PROGRESS": 8, "PENDING": 2, "RESOLVED": 14, "CLOSED": 8 }
  },
  "sla": { "tracked": 20, "on_time": 12, "due_soon": 3, "overdue": 5 },
  "avg_first_response_seconds": 4052,
  "avg_resolution_seconds": null
}
```

`GET /api/dashboard/trends?from=2026-08-05&to=2026-09-03` → `200`:
```json
{
  "range": { "from": "2026-08-05", "to": "2026-09-03", "timezone": "Asia/Ho_Chi_Minh", "granularity": "day" },
  "buckets": [
    { "bucket": "2026-08-05", "statuses": { "OPEN": 2, "IN_PROGRESS": 0, "PENDING": 0, "RESOLVED": 0, "CLOSED": 1 } },
    { "bucket": "2026-08-06", "statuses": { "OPEN": 0, "IN_PROGRESS": 3, "PENDING": 0, "RESOLVED": 1, "CLOSED": 0 } }
  ]
}
```
Notes: `avg_*` are whole seconds — rounded with `int(round(value))` — or `null` when no qualifying ticket. All 5 status keys are always present (0-filled) in `by_status` and in **every** trend bucket, empty or not. `by_status[RESOLVED]+by_status[CLOSED]` is the "Đã giải quyết/Đóng" card. `range` mirrors the resolved window (code names `from_date`/`to_date`; the wire keys `from`/`to` are aliases; the FE renders the label and `range.granularity` selects the axis unit).

---

### Task 1: Scope wrapper + reporting timezone + window resolver (pure)

**Files:**
- Modify: `backend/app/services/ticket_service.py:142-177` (list_tickets) and add the wrapper near `_scope_conds` (`:73-81`).
- Modify: `backend/app/core/config.py` (add `reporting_timezone`).
- Create: `backend/app/services/dashboard_logic.py`.
- Test: `backend/tests/unit/test_dashboard_logic.py`; existing unit + integration scope suites must stay green.

**Interfaces:**
- Produces: `ticket_service.build_ticket_scope_conditions(session, *, user) -> list`, `Settings.reporting_timezone`, `dashboard_logic.resolve_window(...)`.

- [x] **Step 1: Write the failing unit tests for `resolve_window`** (day boundaries in Asia/Ho_Chi_Minh → UTC; default 30-day window; `from > to` raises; `to` clamped when in the future).

```python
# backend/tests/unit/test_dashboard_logic.py
from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import dashboard_logic as dl

UTC = timezone.utc
# Asia/Ho_Chi_Minh is UTC+7, no DST, so a local midnight maps deterministically.


def test_resolve_window_converts_hcm_midnights_to_utc():
    f, t = dl.resolve_window(date(2026, 8, 5), date(2026, 8, 5),
                             now=datetime(2026, 8, 10, tzinfo=UTC),
                             tz_name="Asia/Ho_Chi_Minh")
    # 2026-08-05 00:00 +07 == 2026-08-04 17:00 UTC; exclusive end = next day midnight.
    assert f == datetime(2026, 8, 4, 17, 0, tzinfo=UTC)
    assert t == datetime(2026, 8, 5, 17, 0, tzinfo=UTC)


def test_resolve_window_defaults_to_rolling_30_days():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)  # local date 2026-08-10
    f, t = dl.resolve_window(None, None, now=now, tz_name="Asia/Ho_Chi_Minh")
    assert f == datetime(2026, 7, 11, 17, 0, tzinfo=UTC)   # local (today-29) midnight
    assert t == datetime(2026, 8, 10, 17, 0, tzinfo=UTC)   # local tomorrow midnight


def test_resolve_window_rejects_from_after_to():
    with pytest.raises(ValueError):
        dl.resolve_window(date(2026, 8, 6), date(2026, 8, 5),
                          now=datetime(2026, 8, 10, tzinfo=UTC),
                          tz_name="Asia/Ho_Chi_Minh")


def test_resolve_window_clamps_future_to_today():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    f, t = dl.resolve_window(date(2026, 8, 9), date(2026, 12, 31),
                             now=now, tz_name="Asia/Ho_Chi_Minh")
    assert t == datetime(2026, 8, 10, 17, 0, tzinfo=UTC)  # clamped to local today+1
```

- [x] **Step 2: Run them to verify they fail.**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_dashboard_logic.py -q`
Expected: FAIL — `ModuleNotFoundError`/`AttributeError: module 'app.services' has no attribute 'dashboard_logic'`.

- [x] **Step 3: Add `reporting_timezone` to Settings** (`backend/app/core/config.py`, near `sla_due_soon_minutes:50`).

```python
    # Reporting (S5 dashboard): day boundaries are resolved in this IANA zone.
    reporting_timezone: str = "Asia/Ho_Chi_Minh"
```

- [x] **Step 4: Create `backend/app/services/dashboard_logic.py`** implementing the resolver. Use `zoneinfo.ZoneInfo` (stdlib). Clamp `to` to today only when a caller-supplied `to` is later than today; when both are None use `to = today`, `from = today - (default_days - 1)`.

```python
"""Pure dashboard math: reporting-window resolution and granularity.

No DB imports. Everything takes explicit `now` so unit tests are deterministic.
Day boundaries are resolved in the reporting IANA timezone (default Asia/Ho_Chi_Minh)
then converted to UTC for SQL filters: created_at >= from_utc AND created_at < to_excl_utc.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def _local_midnight_utc(day: date, tz_name: str) -> datetime:
    local = datetime.combine(day, time.min, tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc)


def resolve_window(
    from_date: date | None,
    to_date: date | None,
    *,
    now: datetime,
    tz_name: str,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    """Return (utc_from, utc_to_excl). from_date <= to_date (ValueError otherwise)."""
    tz = ZoneInfo(tz_name)
    today = now.astimezone(tz).date()
    to = to_date or today
    if to > today:
        to = today
    if from_date is None:
        from_date = to - timedelta(days=default_days - 1)
    if from_date > to:
        raise ValueError("from_date must not be after to_date")
    return _local_midnight_utc(from_date, tz_name), _local_midnight_utc(to + timedelta(days=1), tz_name)


def granularity_for(utc_from: datetime, utc_to_excl: datetime) -> str:
    return "day" if (utc_to_excl - utc_from).days <= 62 else "month"
```

- [x] **Step 5: Run the tests to verify they pass.**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit/test_dashboard_logic.py -q`
Expected: PASS (4 passed).

- [x] **Step 6: Add the public scope wrapper in `ticket_service.py`** (immediately below `_scope_conds`, `:81`) and refactor `list_tickets` to use it.

```python
async def build_ticket_scope_conditions(session: AsyncSession, *, user: User) -> list:
    """Public scope builder for list AND dashboard (FR-REP-11): identical SQL.

    Wraps the private _view_team_ids + _scope_conds so dashboard_service reuses
    the exact Ticket List scope (incl. the MANAGER no-team intake rule) without
    importing _-private helpers or duplicating logic.
    """
    view_ids = await _view_team_ids(session, user)
    return _scope_conds(user, view_ids)
```

Replace the first two lines of `list_tickets` (`:145-146`):

```python
    conds = await build_ticket_scope_conditions(session, user=user)
```

- [x] **Step 7: Run the whole scope-relevant suites to prove behavior is unchanged.**

Run: `cd backend && .venv/Scripts/python -m pytest tests/unit -q && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_ticket_service.py tests/integration/test_http_tickets.py -q`
Expected: PASS (existing scoping/listing tests green — wrapper is behavior-identical).

- [x] **Step 8: Commit.**

```bash
git add backend/app/services/ticket_service.py backend/app/core/config.py backend/app/services/dashboard_logic.py backend/tests/unit/test_dashboard_logic.py
git commit -m "feat(s5): ticket scope public wrapper + reporting timezone + pure window resolver"
```

### Task 2: Dashboard service — summary, SLA buckets, averages, trends

**Files:**
- Create: `backend/app/services/dashboard_service.py`.
- Modify: `backend/app/services/dashboard_logic.py` (add `sla_state` and `bucket_labels`; `granularity_for` already in Task 1).
- Create: `backend/tests/integration/test_dashboard.py`.

**Interfaces:**
- Consumes: `ticket_service.build_ticket_scope_conditions`, `dashboard_logic.resolve_window`, `sla_service.deadline_state` + `extend_deadline`.
- Produces: `dashboard_service.summary(session, *, user, from_date, to_date) -> dict` and `dashboard_service.trends(...) -> dict` matching the JSON in the header.

- [x] **Step 1: Add `sla_state()` to `dashboard_logic.py`** with unit tests first (same file as Task 1). Algorithm (verbatim contract):

```python
def sla_state(*, status, first_response_at, first_response_due_at, resolution_due_at,
              pause_on_pending, pending_since, now, due_soon_minutes):
    """SLA bucket for ONE current ticket, or None if it is not SLA-tracked.

    Tracked iff status in {OPEN, IN_PROGRESS, PENDING} and the still-relevant
    deadline is set. Primary deadline = first-response due (only while no first
    response yet) else resolution due. While PENDING on a pause_on_pending policy,
    add the open pending window to the effective deadline (mirrors the extension
    ticket_service.change_status applies on exit). ON_TIME/DUE_SOON/OVERDUE are
    mutually exclusive; tracked rows always produce exactly one bucket.
    """
    if status not in ("OPEN", "IN_PROGRESS", "PENDING"):
        return None
    primary = None
    if first_response_at is None and first_response_due_at is not None:
        primary = first_response_due_at
    elif resolution_due_at is not None:
        primary = resolution_due_at
    if primary is None:
        return None
    if (status == "PENDING" and pause_on_pending and pending_since is not None
            and pending_since < now):
        primary = extend_deadline(primary, (now - pending_since).total_seconds())
    state = deadline_state(primary, now, due_soon_minutes)  # overdue|due_soon|on_track|none
    return {"overdue": "OVERDUE", "due_soon": "DUE_SOON", "on_track": "ON_TIME"}.get(state)
```

Unit tests for `sla_state` (`test_dashboard_logic.py`): (a) responded-OPEN → resolution bucket; (b) un-responded OPEN with only `first_response_due_at` past → OVERDUE; (c) `RESOLVED`/`CLOSED`/no-deadline → None (untracked); (d) DUE_SOON boundary at exactly `due_soon_minutes`; (e) paused-PENDING on `pause_on_pending=true` with an open pending window is ON_TIME though the persisted deadline is in the past, and the same ticket with `pause_on_pending=false` is OVERDUE. Add a unit test that the three buckets are never produced for the same input (single return value).

- [x] **Step 2: Add `bucket_labels` (write its unit tests first, same file).** Signature per the Interfaces block; iterate local dates (day granularity) or first-of-month steps (month granularity) from `utc_from.astimezone(tz).date()` through `(utc_to_excl − 1 µs).astimezone(tz).date()`, yielding `date.strftime("%Y-%m-%d")` / `"%Y-%m"`. Tests: a 3-local-day window → 3 labels ending on the `to` day; a month window spanning e.g. 2026-07-29→2026-08-31 → labels `["2026-07","2026-08"]`; a zero-window safety (never returns empty — caller passes from<to so the span has ≥1 day). Assert the labels are **calendar** years (a window around 2026-12-29→2027-01-02 must emit `2026-12` then `2027-01` for month mode, not ISO-week years).

- [x] **Step 3: Write the integration tests for `summary` and `trends`** (`tests/integration/test_dashboard.py`), mirroring the local throwaway-org helper pattern already used by `tests/integration/test_ticket_service.py:69-124` (`_create_org`, `_create_portal_ticket`, `_cleanup_org`). Tests, each traced to a requirement in Task 5's matrix:
  - `test_summary_counts_match_reference_sql_by_role` (FR-REP-01/07/08/09/11): for admin/manager/agent build org + tickets (some assigned to team A/B, some unassigned) in the window; assert `summary()["kpi"]["total"]` and each `by_status` equal a raw `select(status, count)` run under the SAME `build_ticket_scope_conditions` conds. This checks SQL correctness; **it is NOT the scope-parity proof** (see the direct list test below).
  - `test_summary_matches_list_ticket_totals` (FR-REP-11, direct parity): build a dataset where **every** ticket lies inside the window; for each of the 5 statuses call the Ticket List function (`ticket_service.list_tickets(...)`, same `user`, matching status filter, page_size large enough to hold the fixture) and read its returned total; assert each equals `summary()["kpi"]["by_status"][status]` and the sum equals `summary()["kpi"]["total"]`. This proves Dashboard and Ticket List share the exact scope + population on real rows — the same conds alone would not.
  - `test_manager_sees_no_team_pool_like_list_does` (FR-REP-07/11): a manager must count the unassigned ticket (intake rule) and must NOT count team B tickets — parity with the direct list result for the same user.
  - `test_sla_buckets_mutually_exclusive_and_sum_to_tracked` (FR-REP-04): seed tracked OPEN/IN_PROGRESS/PENDING tickets with past/future/near due deadlines; assert `tracked == on_time + due_soon + overdue` and no double-count.
  - `test_sla_paused_pending_uses_effective_deadline` (FR-REP-04, real pause path): create a **real** `SlaPolicy(pause_on_pending=True)` row and point a ticket at it; put the ticket in `PENDING` and insert a real `TicketHistory` row (`event_type="STATUS_CHANGED"`, `new_value="PENDING"`) with a known `created_at` (pending_since); give `resolution_due_at` a past instant that the open pending window pushes past `now`. Assert: with `pause_on_pending=True` the ticket lands in `ON_TIME`; the twin setup with `pause_on_pending=False` lands in `OVERDUE`. This exercises the DB `pending_since` query + `sla_state` together — not only the pure function.
  - `test_average_null_when_no_data` (FR-REP-05): a window containing no responded/resolved tickets → `avg_first_response_seconds is None` and `avg_resolution_seconds is None`; adding one resolved ticket → non-null resolution. Assert the rounded form: a fractional avg is returned as `int(round(value))`.
  - `test_window_filters_by_created_at` (FR-REP-06): a ticket created before `from` (local) is excluded; one created on the `to` day (local) is included (boundary correctness from Task 1).
  - `test_trends_sql_buckets_cover_whole_window` (FR-REP-06): create N tickets with known `created_at` across two local days + a third outside; assert trends returns **one bucket for every day of the resolved range** (empty days included, all five statuses 0) and the populated days carry the exact cohort split.
- [x] **Step 4: Run them to verify they fail** (no service yet). Expected: import error.
- [x] **Step 5: Implement `dashboard_service`.** Both functions share a private `_windowed_conds(session, user, from_date, to_date)` that returns `(conds, utc_from, utc_to_excl)`, where `conds = await build_ticket_scope_conditions(...)` then `conds += [Ticket.created_at >= utc_from, Ticket.created_at < utc_to_excl]`. Compute `kpi` from `select(Ticket.status, func.count(Ticket.id)).where(*conds).group_by(Ticket.status)` (default every status to 0). Compute averages from two aggregates over the same conds with `first_response_at.is_not(None)` / `resolved_at.is_not(None)` via `func.avg(func.extract("epoch", Ticket.first_response_at - Ticket.created_at))`, then return `int(round(value))` when not `None`. Compute SLA in Python: fetch tracked candidates (`status.in_(OPEN, IN_PROGRESS, PENDING)` + `sla_policy_id.is_not(None)`), join `SlaPolicy.pause_on_pending`; for PENDING+pause rows fetch `pending_since` with one grouped query over `TicketHistory` (`event_type == "STATUS_CHANGED"`, `new_value == "PENDING"`, max `created_at`) mirroring `_pending_since` (`ticket_service.py:110-116`), then classify each row with `sla_state`. (SLA is the one Python loop — it is bounded to open tracked candidates, never the whole ticket set.) **`trends` counts in PostgreSQL** — no ticket-row download to count:

```python
label = func.to_char(
    func.date_trunc(gran, Ticket.created_at.op("AT TIME ZONE")(tz)),
    "YYYY-MM-DD" if gran == "day" else "YYYY-MM",  # calendar, matches bucket_labels()
)
rows = (await session.execute(
    select(label.label("bucket"), Ticket.status, func.count(Ticket.id).label("n"))
    .where(*windowed_conds)
    .group_by(label, Ticket.status)
)).all()
```

  then in Python only: start from `bucket_labels(utc_from, utc_to_excl, tz_name=tz, granularity=gran)`, initialize each label's five status keys to 0, overlay `rows` (indexed by label+status), and emit the ordered list — **every** day/month in the resolved range is present even when it has zero rows. Read `tz` and `due_soon` from `get_settings().reporting_timezone` / `.sla_due_soon_minutes`.
- [x] **Step 6: Run the integration suite to verify it passes** (Task 5 command). Expected: PASS (≈6 new integration tests).
- [x] **Step 7: Commit.**

```bash
git add backend/app/services/dashboard_logic.py backend/app/services/dashboard_service.py backend/tests/integration/test_dashboard.py
git commit -m "feat(s5): dashboard summary/trends service with role scope, SLA buckets, avg times"
```

### Task 3: Dashboard schemas, router, deps scope, main wiring (+ HTTP tests)

**Files:**
- Create: `backend/app/schemas/dashboard.py`, `backend/app/api/dashboard.py`, `backend/tests/integration/test_http_dashboard.py`.
- Modify: `backend/app/core/deps.py:26`, `backend/app/main.py:4-13,46`.

**Interfaces:**
- Consumes: Task 1 + Task 2 function names; `require_roles` (`deps.py:65-72`), `get_session`.
- Produces: `GET /api/dashboard/summary`, `GET /api/dashboard/trends` (HTTP, staff-all), response models `SummaryResponse` / `TrendsResponse`.

- [x] **Step 1: Update `_FEATURE_SCOPES["dashboard"]`** to `{"AGENT", "MANAGER", "ADMIN"}` (`deps.py:26`).
- [x] **Step 2: Write `schemas/dashboard.py`** mirroring the header JSON exactly (wire keys stay `from`/`to`; Python names never collide). Pydantic v2 `BaseModel` like `schemas/ticket.py:10-35`, plus the alias config:

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RangeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    timezone: str
    granularity: Literal["day", "month"]


class KpiOut(BaseModel):
    total: int
    by_status: dict[str, int]  # exactly the 5 status keys, 0-filled


class SlaOut(BaseModel):
    tracked: int
    on_time: int
    due_soon: int
    overdue: int


class SummaryResponse(BaseModel):
    range: RangeOut
    kpi: KpiOut
    sla: SlaOut
    avg_first_response_seconds: int | None
    avg_resolution_seconds: int | None


class TrendBucketOut(BaseModel):
    bucket: str  # "YYYY-MM-DD" | "YYYY-MM"
    statuses: dict[str, int]  # exactly the 5 status keys, 0-filled


class TrendsResponse(BaseModel):
    range: RangeOut
    buckets: list[TrendBucketOut]
```
- [x] **Step 3: Write the HTTP tests first** (`tests/integration/test_http_dashboard.py`, mirror `tests/integration/test_http_ai.py`'s `httpx.ASGITransport` client + `_token()` helper):
  - `test_dashboard_requires_auth`: no bearer → 401.
  - `test_dashboard_denied_non_staff_roles`: login a seeded user of each role; a customer-role/nonexistent feature must not exist — assert the 3 staff roles pass (200) and that a 4th non-staff token (none exists) is out of scope; instead assert `AGENT/MANAGER/ADMIN` each reach both endpoints with 200.
  - `test_summary_and_trends_shape` (admin): 200; body matches the response-model contract (all keys, 0-filled statuses).
  - `test_http_validation_envelope_for_both_bad_ranges`: (a) inverted range `?from=2026-09-09&to=2026-09-01` → 422 with our `AppError` envelope `{"error_code": "VALIDATION_ERROR", "message": "Khoảng thời gian không hợp lệ.", "details": null}`; (b) malformed `?from=not-a-date` → 422 whose body is whatever the **existing shared** `register_exception_handlers` produces for `RequestValidationError` (read `app/core/errors.py` to pin the exact `error_code`/`details` shape before asserting). The two cases may have different `details`; both must carry the repo's standard envelope keys — never a Dashboard-only error format.
  - `test_http_summary_exact_counts_per_role`: seed a fixed dataset whose per-role expected totals are computed up front from the fixture; assert admin/manager/agent each return the **exact** expected `kpi.total` (no `admin ≥ manager ≥ agent` inequality — the scopes are not subset-related on arbitrary data, so only fixture-exact counts are meaningful).
- [x] **Step 4: Run them to verify they fail** (no router yet).
- [x] **Step 5: Implement `api/dashboard.py`.** `router = APIRouter(tags=["dashboard"])`; `@router.get("/dashboard/summary", response_model=SummaryResponse)` and `@router.get("/dashboard/trends", response_model=TrendsResponse)`. Declare the query params with aliases (never a Python identifier named `from`): `from_date: date | None = Query(default=None, alias="from")`, `to_date: date | None = Query(default=None, alias="to")`. FastAPI coerces `YYYY-MM-DD`; a malformed string 422s through the **shared** `RequestValidationError` handler in `app/core/errors.py` — no new handler. Call `dashboard_service.summary(session, user=..., from_date=from_date, to_date=to_date)`; catch `ValueError` from `resolve_window` → `AppError(422, "VALIDATION_ERROR", "Khoảng thời gian không hợp lệ.")`. Wrap `require_roles("AGENT", "MANAGER", "ADMIN")`. No rate limit.
- [x] **Step 6: Register the router in `main.py`** (`from app.api.dashboard import router as dashboard_router` and `application.include_router(dashboard_router, prefix="/api")` after `ai_router`, mirroring `main.py:46`).
- [x] **Step 7: Run the HTTP suite to verify it passes.**

Run: `cd backend && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q`
Expected: PASS (new HTTP tests ≈5; whole folder green).

- [x] **Step 8: Commit.**

```bash
git add backend/app/schemas/dashboard.py backend/app/api/dashboard.py backend/app/core/deps.py backend/app/main.py backend/tests/integration/test_http_dashboard.py
git commit -m "feat(s5): dashboard HTTP API (summary/trends), AGENT in dashboard feature scope"
```

### Task 4: Frontend DashboardPage + trend chart + route/guard/nav

**Files:**
- Create: `frontend/src/pages/DashboardPage.jsx`, `frontend/src/components/DashboardTrendChart.jsx`, `frontend/src/styles/dashboard.css`.
- Modify: `frontend/src/App.jsx:45-52`, `frontend/src/app/AppShell.jsx:6-10`, `frontend/src/app/Landings.jsx`.

**Interfaces:**
- Consumes: `api.get` from `frontend/src/api/client.js`; `STATUS_LABELS` from `lib/labels.js`; CSS tokens (`tokens.css`); the two response shapes above.
- Produces: `<DashboardPage/>` used by route `/app/dashboard`.

- [x] **Step 1: Write the route + guard + nav edits first.**
  - `App.jsx:45-52`: change `roles={['MANAGER','ADMIN']}` → `roles={['AGENT','MANAGER','ADMIN']}` and `element={<ManagerLanding />}` → `element={<DashboardPage />}` (add the import). Ensure no other route still imports `ManagerLanding`; delete the now-unrouted `ManagerLanding` export in `Landings.jsx` (keep `AdminLanding` + `Placeholder` for `/app/admin`, S6).
  - `AppShell.jsx:6-10`: NAV dashboard row roles → `['AGENT','MANAGER','ADMIN']` so an AGENT sees the "Bảng điều khiển" item.
- [x] **Step 2: Write `DashboardPage.jsx`** with a single `load()` that fires **both** fetches together and renders the pair atomically, following the fetch/loading/error/empty conventions of `TicketsListPage.jsx:30-66`. Toolbar = preset buttons (7/30/90/180/365, default 30; no "Tất cả") plus two `<input type="date">` for start/end; the same date pair drives both calls. Presets compute `to = today`, `from = to − (N−1)` using **local** (browser) dates. Local-date formatting must use calendar getters, never UTC slicing:
```js
const pad = (n) => String(n).padStart(2, '0');
const fmtLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
// NOT d.toISOString().slice(0, 10): toISOString shifts to UTC and can flip the day.
```
  Concurrency guard — a fast preset switch must not let a stale response overwrite a newer one. Keep a module/render-level `loadSeq` counter; `const seq = ++loadSeq` before fetching; after each await, `if (seq !== loadSeq) return;` before `setState` (or abort the previous request via an `AbortController` and re-create it per load; if `api.get` does not accept a signal, the sequence guard alone is enough). Fetch with `Promise.all` and set both summary + trends in one state update.
  Sections: KPI card row (Tổng · Mở · Đang xử lý · Chờ bổ sung thông tin · Đã giải quyết/Đóng · Quá hạn SLA); a compact SLA strip (Trong hạn / Sắp quá hạn / Quá hạn / đang theo dõi); an averages row rendering "Chưa có dữ liệu" whenever the API value is `null`; and the trend chart card titled with a note that counts are "theo trạng thái hiện tại". **Empty state**: when `summary.kpi.total === 0` show "Chưa có dữ liệu trong khoảng thời gian này" in the cards/chart area. The page renders backend buckets verbatim — it never adds a bucket it did not receive nor a status key the API omitted. Handle the 422 from the backend for an inverted range by showing the error message inline.
- [x] **Step 3: Write `DashboardTrendChart.jsx`** — pure hand-drawn stacked SVG: props `{buckets, granularity, labels}`; map each bucket to a `<rect>` stack of five status segments using status colors from tokens (add CSS classes in `dashboard.css`), x-axis ticks (day labels for ≤~14 buckets, else sparse), y-axis gridlines from the max count, `<title>`/aria on groups, and `viewBox` scaling so the page never scrolls horizontally (`overflow-x: auto` wrapper). No external chart/dependency.
- [x] **Step 4: Write `dashboard.css`** reusing tokens (`--color-surface/border/text/...`, status palette like `tickets.css:17-28`), adding explicit light + dark token blocks and `.kpi-card`, `.kpi-value`, `.kpi-label`, `.sla-chip`, `.avg-cell`, `.chart-card`, `.trend-legend` classes. Add `import '../styles/dashboard.css'` at the top of `DashboardPage.jsx`.
- [x] **Step 5: Build to verify no syntax/route errors.**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [x] **Step 6: Manual smoke via the run skill (live stack on :8080 or Vite :5173).** Login as `admin@example.com` → open "Bảng điều khiển"; then `hung.manager@example.com`; then `lan.agent@example.com` — each sees the page with scoped numbers and 2-theme rendering.
- [x] **Step 7: Commit.**

```bash
git add frontend/src/pages/DashboardPage.jsx frontend/src/components/DashboardTrendChart.jsx frontend/src/styles/dashboard.css frontend/src/App.jsx frontend/src/app/AppShell.jsx frontend/src/app/Landings.jsx
git commit -m "feat(s5): dashboard page — KPIs, SLA strip, averages, SVG status trends; AGENT nav access"
```

### Task 5: Acceptance — README demo block, FR-REP traceability, gates

**Files:**
- Modify: `README.md` (add S5 block after the S4 block, ~`README.md:66`), this plan file (check off tasks), and `docs/superpowers/specs/2026-09-02-ai-customer-support-design.md` only if a decision contradicts it (it should not).

- [x] **Step 1: Add the S5 README demo block** (Vietnamese), mirroring the S4 block's style: endpoints summary, role scope table (Agent = bản thân + nhóm; Manager = nhóm quản lý + vé chưa gán nhóm; Admin = toàn hệ thống), "theo trạng thái hiện tại" note on the chart, avg null → "Chưa có dữ liệu", demo quick-start (login admin / manager / agent → open Bảng điều khiển). Add one honest line: NFR-PER-06 (P95 ≤ 5 s/12 tháng) **chưa có performance test** — bản demo chỉ là functional smoke test, không phải bằng chứng về NFR.
- [x] **Step 2: Verify the full gate set.**

Run (from `backend`): `docker compose exec backend alembic check` — Expected: `No new upgrade operations detected.` (no migration added).
Run: `cd backend && .venv/Scripts/python -m pytest tests/unit -q` — Expected: PASS (unit 84 + Task 1/2 unit tests).
Run: `cd backend && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q` — Expected: PASS; **report the authoritative per-file integration split in the plan report** (S3/S4 precedent: reconcile actual counts, e.g. add `dashboard N` + `http_dashboard N`).
Run: `cd frontend && npm run build` — Expected: succeeds.
Run live demo on the running demo stack (:8080) — login as admin / hung.manager / lan.agent and confirm scoped numbers, "Chưa có dữ liệu" when no resolved ticket in window, and 2-theme chart.
Perf: **no official P95 result** — the gate above is a functional smoke test only; do NOT write "NFR-PER-06 satisfied" anywhere (report line: "chưa xác nhận P95 chính thức — cần performance test riêng").

- [x] **Step 3: FR-REP traceability (fill the matrix, one check per line).**
  | Req | Where satisfied | Test |
  |---|---|---|
  | FR-REP-01 total-by-scope | summary.kpi.total | summary-reference-SQL & http scope tests |
  | FR-REP-02 by status | summary.kpi.by_status | summary-reference-SQL test |
  | FR-REP-04 SLA 3 buckets | summary.sla | mutual-exclusivity & tracked-sum test |
  | FR-REP-05 avg first/resolution | summary.avg_* (null semantics) | avg-null test + FE "Chưa có dữ liệu" |
  | FR-REP-06 time filter | resolve_window + presets | boundary test + HTTP 422 + FE presets |
  | FR-REP-07 manager own teams | scope wrapper (manager) | manager parity + no-team test |
  | FR-REP-08 agent scope | scope wrapper (agent) | agent reference-SQL test |
  | FR-REP-09 admin whole system | scope wrapper (admin=[]) | admin reference-SQL test |
  | FR-REP-11 same defs as detail | build_ticket_scope_conditions single source | every reference-SQL test uses the same wrapper |
- [x] **Step 4: Commit README + plan check-offs.**

```bash
git add README.md docs/superpowers/plans/2026-09-03-s5-dashboard.md
git commit -m "docs(s5): dashboard demo block + acceptance gates + FR-REP traceability"
```

---

## Self-Review (writing-plans)

**1. Spec coverage.** §10 S5 deliverable → Task 3 endpoints + Task 2 service + Task 4 FE + Task 5 demo/README. FR-REP 01/02/04/05/06/07/08/09/11 → Task 2/3 + matrix in Task 5. FR-REP-03/10/12 excluded by user decision. NFR-PER-06 → day/month switch at ≤62 days and no server-side range cap; **P95 is never claimed** — there is no performance test, so every gate/README word says "chưa xác nhận chính thức". UC-13 actor=Agent included (Task 1/3 deps + Task 4 nav/guard). SLA pause-on-pending is handled in `sla_state` AND exercised end-to-end by a real-policy integration test (`test_sla_paused_pending_uses_effective_deadline`), because seed policies are all `pause_on_pending=false`.

**2. Placeholder scan.** Every task names concrete files (created/modified), exact function signatures, response JSON, test names, and runnable verification commands. The two larger modules (Task 2 service internals, Task 4 FE chart) are specified by responsibility + precise sub-queries/sub-components rather than full transcription — an implementer opens the cited existing files (which this plan's contracts reference by name:line) to fill body code, matching how S3/S4 plan briefs already point at the live codebase. No TBD/TODO/"implement later" left: each step carries either code, a test name, an expected output, or a concrete mirror-target.

**3. Type consistency.** `resolve_window` returns `(datetime, datetime)` used as `utc_from/utc_to_excl` in every SQL filter; `sla_state` returns exactly the 3 bucket strings or `None` (tracked counters); `bucket_labels` returns `YYYY-MM-DD`/`YYYY-MM` labels that **byte-match** the PostgreSQL `to_char(date_trunc(...))` output the trends `GROUP BY` emits, so the Python fill overlay and the SQL counts line up per bucket; `build_ticket_scope_conditions` is the one scope entry point consumed by `list_tickets`, `dashboard_service`, the reference-SQL tests, and the direct `list_tickets` parity test; `RangeOut` fields are `from_date`/`to_date` (aliases `from`/`to`) used identically by the router's `Query(alias=...)` params and the service args.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-03-s5-dashboard.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, two-stage review between tasks (this repo's S0-S4 pattern via `.superpowers/sdd/…`).

**2. Inline Execution** — run tasks in this session with checkpoints (executing-plans).

Which approach?
