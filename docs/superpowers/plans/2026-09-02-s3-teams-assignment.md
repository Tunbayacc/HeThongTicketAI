# S3 — Teams & Assignment (Phân công) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the S2 minimal-assign into the full assignment workflow the design spec §10 S3 and SRS §4.4 (FR-ASG-01..10) require: valid assignee enforcement, reassignment history, a "needs reassignment" state surfaced when an assignee is deactivated, and team-aware list/detail readouts.

**Architecture:** Builds directly on the S2 ticket service/routers/schemas (accepted HEAD `7902f81`). S3 adds (a) a pure assignment-policy module, (b) assignee-validation hardening inside `assign_ticket`, (c) derived `needs_reassignment` + `team_name`/`assignee_name` readouts on the staff list/detail and a `team_id` list filter, (d) `role`/`is_active` on the team-picker payload, (e) FE assignment readout/banner/picker + a list "Nhóm / Phụ trách" column + team filter. No Alembic migration: `needs_reassignment` is *derived* from `tickets.assigned_to` + `users.is_active` + `tickets.status` — the same shape as S2's pause-on-pending derivation (Controller decision 3 in the S2 plan).

**Tech Stack:** FastAPI + Pydantic · PostgreSQL + SQLAlchemy async · React + Vite + Vanilla CSS (NO Tailwind) · Docker Compose. No new dependency.

## Global Constraints

- Stack fixed: FastAPI + Pydantic · PostgreSQL + SQLAlchemy async · React + Vite + Vanilla CSS (NO Tailwind) · Docker Compose. No new dependency in S3 (no change to `pyproject.toml` / `requirements`).
- **No new Alembic migration in S3.** `alembic check` must stay `No new upgrade operations detected.` `needs_reassignment` is derived — do NOT add a column or ORM-mapped column; do NOT add ORM `relationship` attributes that map columns (prefer explicit lookups to be safe).
- Roles exactly AGENT/MANAGER/ADMIN. Wrong role → `403 ACCESS_DENIED`. Out-of-scope OR unknown ticket → `404 TICKET_NOT_FOUND` (anti-leak, unchanged from S2). Manager may assign only into a team they manage (already enforced); Admin may assign to any active team; AGENT may not assign at all (route role gate `MANAGER_ADMIN`, unchanged).
- **Assignee validity (FR-ASG-02/03):** when `assigned_to` is provided the assignee must be (i) a real user who is `is_active`, (ii) `role == 'AGENT'`, and (iii) an active member (`team_members.is_active` true) of the target team. Violation → `400 ASSIGNEE_NOT_IN_TEAM` (SRS §10.2 code; FE already maps it). Assigning a team without an assignee stays allowed. Assignment never changes `status`/`resolved_at`/`closed_at` (FR-ASG-10).
- **`needs_reassignment` (FR-ASG-09, derived):** true iff `assigned_to IS NOT NULL` AND `status ∈ {OPEN, IN_PROGRESS, PENDING}` AND the assignee user `is_active = false`. RESOLVED/CLOSED or unassigned or active-assignee ⇒ false. Derived at read time — the readout flips the moment the assignee is (de)activated; reassigning to an active AGENT clears it automatically. Public track (`/api/public/track`) must NOT expose it or team/assignee names (FR-PUB-06/07 anti-leak).
- Error envelope uniform `{error_code, message, details}`; business codes only from SRS §10.2 (`ASSIGNEE_NOT_IN_TEAM`, `ACCESS_DENIED`, `TICKET_NOT_FOUND`, `VERSION_CONFLICT`, `VALIDATION_ERROR`); transport codes from `errors._FALLBACK`.
- Timestamps TIMESTAMPTZ UTC stored, ISO 8601 UTC on wire. Team/assignee ids stay UUID strings on the wire.
- Every business-field write keeps appending a `ticket_history` row (old/new/actor/time/reason) + an `audit_logs` row (PII-free). Reassignment = a NEW `ASSIGNED` history row whose `old_value`/`new_value` snapshot the previous→next `{team_id, assigned_to}` (FR-ASG-07/08). Do not break the existing write/commit/refresh rhythm or the `MissingGreenlet` discipline (eager-load anything read synchronously; prefer `session.get`/explicit queries for name lookups).
- UI Vietnamese labels / English identifiers; loading/empty/success/error states; double-submit disabled. New readouts reuse existing tokens/classes in `styles/tokens.css` + `styles/tickets.css` — add classes only if a token combo cannot express the state.
- S2 behavior must not regress: S2 unit (51) + integration (16) stay green; list/detail schemas only GAIN optional fields (any test asserting an exact key-set on those responses may need its expectation widened — verify, don't delete coverage).
- Demo stack stays: db `:5433`, backend `:8001`, frontend `:8080`. Foreign `hethongticketai` stack (5432/8000/5173) + native postgres + `docker compose down` NEVER touched. Seed identities (committed, README-documented, non-secret): `hung.manager@example.com` manages **Team Kỹ thuật** (agents `lan.agent@example.com`, `minh.agent@example.com`); `ha.manager@example.com` manages **Team Tài khoản & Thanh toán** (agents `dat.agent`, `ngoc.agent`). Never print env secrets.

## Controller decisions (S3, ratified — bind every task)

1. **`needs_reassignment` is DERIVED, not stored** (no migration, no column). Pure predicate in a new `assignment.py`; list/detail compute it at read time from the assignee's `is_active` + `status`. Mirrors S2 pause-on-pending derivation. Alembic stays clean.
2. **Assignee must be an active AGENT** of the target team (FR-ASG-02/03): the S2 check only required an active `team_members` row. S3 additionally requires `users.is_active` and `users.role == 'AGENT'`, raising the SAME `400 ASSIGNEE_NOT_IN_TEAM` (one code, FE message already exists). Team-only assignment (no `assigned_to`) is unchanged. Seeded demo tickets whose assignee happens to be a manager are historical rows and stay untouched.
3. **`/api/teams` member payload gains `role` + `is_active`** (additive fields on `TeamMemberOut`, from `m.user.role` / `m.user.is_active`). The FE assignee picker disables (but still shows) members who are not an active AGENT. Existing consumers only read `id`/`full_name`/`team_role`, so this is backward-compatible.
4. **`team_id` list filter is scope-safe:** adding `Ticket.team_id == X` under the caller's existing scope ORs means an out-of-scope team can only ever yield rows the caller could already see (no existence leak). Invalid uuid → `422 VALIDATION_ERROR` (the caller's own input, not a resource probe).
5. **Detail/list enrichment is staff-only.** `team_name`, `assignee_name`, `needs_reassignment` are added to `TicketDetail` + `TicketListItem` (staff schemas) and computed in the router/service mappers. The public track mapper is untouched.

---

## File structure (locked)

Backend:
- Create `backend/app/services/assignment.py` — pure assignment policy (open-status set, `needs_reassignment`, `is_valid_assignee`).
- Test `backend/tests/unit/test_assignment.py`.
- Modify `backend/app/services/ticket_service.py` — `assign_ticket` hardening + `list_tickets` `team_id` filter + item enrichment.
- Modify `backend/app/schemas/ticket.py` — `TicketListItem`/`TicketDetail` gain `team_name`, `assignee_name`, `needs_reassignment`; `TeamMemberOut` gains `role`, `is_active`.
- Modify `backend/app/api/tickets.py` — `team_id` query param on GET `/tickets`; `_to_detail` name/flag enrichment; `/teams` mapper sets the two new member fields.
- Modify `backend/tests/integration/test_ticket_service.py` — assignee validation + reassign history + FR-ASG-10 service tests.
- Modify `backend/tests/integration/test_http_tickets.py` — enrichment + team-filter + derived-flag + `/teams` payload HTTP tests.

Frontend:
- Modify `frontend/src/pages/TicketDetailPage.jsx` — assignment readout in header, needs-reassignment banner + "Phân công lại" CTA, assignee `<option disabled>` for non-active/non-AGENT members.
- Modify `frontend/src/pages/TicketsListPage.jsx` — "Nhóm / Phụ trách" column, needs-reassignment badge, team filter (MANAGER/ADMIN).
- Modify `frontend/src/styles/tickets.css` — only if a new visual state needs it (banner class / needs-reassign cell emphasis).

Docs:
- Modify `README.md` — S3 block after the S2 block.

---

### Task 1: Pure assignment policy helpers + unit tests

**Why one task:** put the S3 business predicates in a zero-dependency pure module first (TDD), so Tasks 2–3 only consume tested helpers.

**Files:**
- Create: `backend/app/services/assignment.py`
- Create: `backend/tests/unit/test_assignment.py`

**Interfaces:**
- Produces (consumed by Task 2 `assign_ticket` and Task 3 enrichment): `OPEN_STATUSES: frozenset[str]`, `is_open_status(status: str) -> bool`, `needs_reassignment(*, assigned_to: bool, status: str, assignee_active: bool | None) -> bool`, `is_valid_assignee(*, role: str, user_active: bool, membership_active: bool) -> bool`.

- [ ] **Step 1: Write the failing unit test**

Create `backend/tests/unit/test_assignment.py`:

```python
"""Unit: S3 assignment policy predicates (pure, no DB)."""

from app.services.assignment import (
    OPEN_STATUSES,
    is_open_status,
    is_valid_assignee,
    needs_reassignment,
)


def test_open_statuses_are_only_the_three_active_states():
    assert OPEN_STATUSES == frozenset({"OPEN", "IN_PROGRESS", "PENDING"})
    for s in OPEN_STATUSES:
        assert is_open_status(s) is True
    for s in ("RESOLVED", "CLOSED", "ARCHIVED", ""):
        assert is_open_status(s) is False


def test_needs_reassignment_true_only_when_open_with_inactive_assignee():
    # The FR-ASG-09 core: an open ticket whose assignee user is disabled.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=False) is True
    assert needs_reassignment(assigned_to=True, status="IN_PROGRESS", assignee_active=False) is True
    assert needs_reassignment(assigned_to=True, status="PENDING", assignee_active=False) is True


def test_needs_reassignment_false_when_active_or_unassigned_or_closed():
    # Active assignee -> no flag; no assignee -> no flag.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=True) is False
    assert needs_reassignment(assigned_to=False, status="OPEN", assignee_active=False) is False
    # Resolved/closed tickets are out of the reassignment pool regardless.
    assert needs_reassignment(assigned_to=True, status="RESOLVED", assignee_active=False) is False
    assert needs_reassignment(assigned_to=True, status="CLOSED", assignee_active=False) is False


def test_needs_reassignment_unknown_assignee_is_false():
    # assignee_active=None => the assignee row is missing/deleted => not flaggable.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=None) is False


def test_is_valid_assignee_requires_active_agent_member():
    assert is_valid_assignee(role="AGENT", user_active=True, membership_active=True) is True
    assert is_valid_assignee(role="MANAGER", user_active=True, membership_active=True) is False
    assert is_valid_assignee(role="AGENT", user_active=False, membership_active=True) is False
    assert is_valid_assignee(role="AGENT", user_active=True, membership_active=False) is False
    assert is_valid_assignee(role="ADMIN", user_active=True, membership_active=True) is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_assignment.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.assignment'`.

- [ ] **Step 3: Write the minimal implementation**

Create `backend/app/services/assignment.py`:

```python
"""S3 assignment policy predicates (pure, zero-DB).

Task 1 unit-tests these; assign_ticket (Task 2) and the list/detail mappers
(Task 3) consume them. `needs_reassignment` is DERIVED, never stored (Controller
decision 1): the S3 slice has no admin deactivation endpoint yet, so a stored
flag would be dead code reachable only from SQL; deriving from users.is_active
+ tickets.status means the readout is correct the moment an assignee is
(de)activated and clears itself on reassignment to an active AGENT.
"""

# Statuses that count as an *open* ticket for the reassignment pool (FR-ASG-09).
OPEN_STATUSES = frozenset({"OPEN", "IN_PROGRESS", "PENDING"})


def is_open_status(status: str) -> bool:
    return status in OPEN_STATUSES


def needs_reassignment(*, assigned_to: bool, status: str,
                       assignee_active: bool | None) -> bool:
    """An open ticket whose assignee user is disabled must be flagged for
    reassignment (FR-ASG-09). assignee_active=None => assignee row missing
    (deleted) => not flaggable. Closed/resolved tickets are out of the pool."""
    return bool(assigned_to) and is_open_status(status) and assignee_active is False


def is_valid_assignee(*, role: str, user_active: bool, membership_active: bool) -> bool:
    """A valid assignee is an active Support Agent with an active membership of
    the target team (FR-ASG-02/03)."""
    return role == "AGENT" and user_active and membership_active
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit/test_assignment.py -q`
Expected: **5 passed**.

- [ ] **Step 5: Run the whole unit suite (no regressions)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: **56 passed** (51 + 5 new).

- [ ] **Step 6: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/services/assignment.py backend/tests/unit/test_assignment.py
git commit -m "feat(backend): S3 assignment policy predicates (open status, needs_reassignment, valid assignee)
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: assign_ticket hardening — active-AGENT assignee + reassign history + FR-ASG-10

**Why one task:** close FR-ASG-02/03 (assignee must be an active AGENT of the team), prove FR-ASG-08 (reassignment preserves full history) and FR-ASG-10 (assignment never auto-resolves/closes) at the service layer.

**Files:**
- Modify: `backend/app/services/ticket_service.py` (import + `assign_ticket` body)
- Modify: `backend/tests/integration/test_ticket_service.py` (append tests)

**Interfaces:**
- Consumes: `assignment.is_valid_assignee` from Task 1.
- Produces: `assign_ticket` keeps its exact signature `(session, *, ticket, actor, team_id, assigned_to, reason, expected_version) -> Ticket`. Behavior additions only.

- [ ] **Step 1: Write the failing service tests**

Append to `backend/tests/integration/test_ticket_service.py` (reuse the existing module helpers `_tag`, `_add_user`, `_add_team`, `_add_membership`, `_create_org`, `_create_portal_ticket`, `_cleanup_org`, `_remove_ticket`, and the existing imports `AppError`, `delete`, `User`, `Ticket`, `TeamMember`, `TeamRole`, `TicketStatus`, `UserRole`, `AsyncSessionLocal`, `ticket_service`). The org fixture's `agent_a` is AGENT+active in team A; `agent_b` is AGENT+active in team B; `manager` is the MANAGER-role member of team A (a membership row already exists). Append these three tests:

```python
async def test_assign_rejects_inactive_or_non_agent_assignee():
    """FR-ASG-02/03: assignee must be an active Support Agent of the team."""
    org = await _create_org()
    # The org's manager is already the MANAGER-role member of team_a (no new
    # membership row: (team_id, user_id) is unique), so the three bad assignees
    # below exercise role + user-active + membership-active independently.
    disabled = await _add_user(f"off.{_tag()}@example.com", "Agent Vô hiệu hóa", UserRole.AGENT.value)
    await _add_membership(org["team_a"].id, disabled.id, TeamRole.MEMBER.value)
    async with AsyncSessionLocal() as s:
        # Flip the *user* inactive while keeping the membership row active: the
        # S2 check (active membership only) must NOT let this through anymore.
        u = await s.get(User, disabled.id)
        u.is_active = False
        await s.commit()
    ticket = await _create_portal_ticket()
    try:
        for bad, label in (
            (disabled.id, "inactive user"),
            (org["manager"].id, "manager (role != AGENT)"),
            (org["agent_b"].id, "agent outside the team"),
        ):
            async with AsyncSessionLocal() as s:
                t = await s.get(Ticket, ticket.id)
                with pytest.raises(AppError) as ei:
                    await ticket_service.assign_ticket(
                        s, ticket=t, actor=org["admin"], team_id=org["team_a"].id,
                        assigned_to=bad, reason=None, expected_version=t.version)
                assert ei.value.status_code == 400
                assert ei.value.error_code == "ASSIGNEE_NOT_IN_TEAM", label
        # A valid active AGENT of the team still succeeds.
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            out = await ticket_service.assign_ticket(
                s, ticket=t, actor=org["admin"], team_id=org["team_a"].id,
                assigned_to=org["agent_a"].id, reason="ok", expected_version=t.version)
            assert out.assigned_to == org["agent_a"].id
    finally:
        await _remove_ticket(ticket.id)
        await _cleanup_org(org, [])
        # `disabled` is not in org["user_ids"], so clean its membership + row too.
        async with AsyncSessionLocal() as s:
            await s.execute(delete(TeamMember).where(TeamMember.user_id == disabled.id))
            await s.execute(delete(User).where(User.id == disabled.id))
            await s.commit()


async def test_reassign_appends_history_and_preserves_snapshot():
    """FR-ASG-08: changing assignee writes a NEW ASSIGNED row with old/new."""
    org = await _create_org()
    agent_c = await _add_user(f"agc.{_tag()}@example.com", "Agent C", UserRole.AGENT.value)
    await _add_membership(org["team_a"].id, agent_c.id, TeamRole.MEMBER.value)
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            await ticket_service.assign_ticket(
                s, ticket=t, actor=org["manager"], team_id=org["team_a"].id,
                assigned_to=org["agent_a"].id, reason="Gán lần đầu", expected_version=t.version)
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            await ticket_service.assign_ticket(
                s, ticket=t, actor=org["manager"], team_id=org["team_a"].id,
                assigned_to=agent_c.id, reason="Đổi người phụ trách", expected_version=t.version)
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            # t.history is lazy="selectin" (loaded on get); refresh keeps it fresh
            # after the second commit. Sort chronologically — relationship order is
            # not guaranteed.
            await s.refresh(t, attribute_names=["history"])
            rows = sorted((h for h in t.history if h.event_type == "ASSIGNED"),
                          key=lambda h: (h.created_at, str(h.id)))
            assert len(rows) == 2, "reassignment must append, never overwrite"
            first, second = rows[0], rows[1]
            # First ASSIGNED snapshot: from empty to agent_a.
            assert first.old_value == {"team_id": None, "assigned_to": None}
            assert first.new_value["assigned_to"] == str(org["agent_a"].id)
            assert first.reason == "Gán lần đầu"
            # Second ASSIGNED snapshot: agent_a -> agent_c (full history preserved).
            assert second.old_value["assigned_to"] == str(org["agent_a"].id)
            assert second.new_value["assigned_to"] == str(agent_c.id)
            assert second.reason == "Đổi người phụ trách"
            assert t.assigned_to == agent_c.id and t.version >= 3
    finally:
        await _remove_ticket(ticket.id)
        await _cleanup_org(org, [])
        # `agent_c` is not in org["user_ids"], so clean its membership + row too.
        async with AsyncSessionLocal() as s:
            await s.execute(delete(TeamMember).where(TeamMember.user_id == agent_c.id))
            await s.execute(delete(User).where(User.id == agent_c.id))
            await s.commit()


async def test_assign_never_changes_status_on_resolved_ticket():
    """FR-ASG-10: assignment is orthogonal to resolution/closure."""
    org = await _create_org()
    ticket = await _create_portal_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            # Reach RESOLVED through the legal state machine (OPEN -> IN_PROGRESS ->
            # RESOLVED), then assign on top of it.
            t = await ticket_service.change_status(
                s, ticket=t, actor=org["admin"], target=TicketStatus.IN_PROGRESS.value,
                reason=None, expected_version=t.version)
            t = await ticket_service.change_status(
                s, ticket=t, actor=org["admin"], target=TicketStatus.RESOLVED.value,
                reason=None, expected_version=t.version)
            assert t.status == TicketStatus.RESOLVED.value and t.resolved_at is not None
        async with AsyncSessionLocal() as s:
            t = await s.get(Ticket, ticket.id)
            out = await ticket_service.assign_ticket(
                s, ticket=t, actor=org["manager"], team_id=org["team_a"].id,
                assigned_to=org["agent_a"].id, reason="gán sau khi resolve", expected_version=t.version)
            assert out.status == TicketStatus.RESOLVED.value, "assign must not change status"
            assert out.resolved_at is not None
    finally:
        await _remove_ticket(ticket.id)
        await _cleanup_org(org, [])
```

- [ ] **Step 2: Run the new tests to verify they fail (validation gap is real)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_ticket_service.py -q -k "rejects_inactive or reassign_appends or never_changes_status"`
Expected: FAIL. `rejects_inactive...` fails because S2 accepts an inactive user whose membership row is active (no `users.is_active`/role check). The other two may pass already — that is fine; they pin the behavior.

- [ ] **Step 3: Harden `assign_ticket`**

In `backend/app/services/ticket_service.py`, add the new import among the existing service imports (after `from app.services.audit import write_audit` is fine):

```python
from app.services.assignment import is_valid_assignee
```

Replace the assignee block inside `assign_ticket` (currently the `if assignee_uuid is not None:` membership check, lines ~358-367) so it first loads the assignee user and requires an active AGENT. The current text to replace is:

```python
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
```

Replace it with:

```python
    if assignee_uuid is not None:
        membership = await session.execute(
            select(TeamMember.id).where(
                TeamMember.team_id == team_uuid, TeamMember.user_id == assignee_uuid,
                TeamMember.is_active.is_(True),
            )
        )
        assignee_user = await session.get(User, assignee_uuid)
        if membership.scalar_one_or_none() is None or assignee_user is None or not is_valid_assignee(
            role=assignee_user.role, user_active=assignee_user.is_active, membership_active=True,
        ):
            raise AppError(400, "ASSIGNEE_NOT_IN_TEAM",
                           "Người được gán phải là Support Agent đang hoạt động trong nhóm đã chọn.")
```

Leave the team-active check, the MANAGER-managed-team check, the snapshot history row, `ticket.version += 1`, and the audit write exactly as they are. Assignment never touches `status`/`resolved_at`/`closed_at`.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_ticket_service.py -q`
Expected: **10 passed** (7 existing + 3 new).

- [ ] **Step 5: Regression — full backend suites + alembic drift**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: **56 passed**.

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q`
Expected: **19 passed** (16 existing + 3 new). Each test removes exactly what it created; the seeded rows are untouched.

Run: `docker compose exec backend alembic check`
Expected: `No new upgrade operations detected.` (no model/column change yet).

- [ ] **Step 6: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/services/ticket_service.py backend/tests/integration/test_ticket_service.py
git commit -m "feat(backend): S3 assignee must be an active AGENT of the team (FR-ASG-02/03); reassign history + FR-ASG-10 pinned
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: List/detail enrichment (team_name, assignee_name, needs_reassignment) + team_id filter + /teams member fields

**Why one task:** the derived flag and assignment readouts are worthless if the API does not expose them, and FR-TIC-06 rows need team/assignee names. This task carries the whole read-side delta (schemas + service + router + HTTP tests) so the FE (Task 4) consumes one coherent contract.

**Files:**
- Modify: `backend/app/schemas/ticket.py` (`TicketListItem`, `TicketDetail`, `TeamMemberOut`)
- Modify: `backend/app/services/ticket_service.py` (`list_tickets` signature + item enrichment)
- Modify: `backend/app/api/tickets.py` (`team_id` query param; `_to_detail` enrichment; `/teams` mapper)
- Modify: `backend/tests/integration/test_http_tickets.py` (append tests)

**Interfaces:**
- Consumes: `assignment.needs_reassignment` (Task 1); unchanged `assign_ticket` (Task 2).
- Produces (consumed by Task 4 FE):
  - `TicketListItem` adds `team_name: str | None`, `assignee_name: str | None`, `needs_reassignment: bool`.
  - `TicketDetail` adds the same three fields.
  - `TeamMemberOut` adds `role: str`, `is_active: bool`.
  - `GET /api/tickets` accepts optional `team_id: str | None` (uuid) — filter scoped under the caller's view (Controller decision 4).

- [ ] **Step 1: Extend the schemas**

In `backend/app/schemas/ticket.py`:

- `TeamMemberOut` — add two fields after `team_role`:

```python
class TeamMemberOut(BaseModel):
    id: str
    full_name: str
    team_role: str  # MANAGER | MEMBER
    role: str       # user role AGENT | MANAGER | ADMIN (S3 assignee picker)
    is_active: bool  # user.is_active (S3: disable non-active assignees)
```

- `TicketListItem` — add three fields after `assigned_to`:

```python
    assigned_to: str | None
    team_name: str | None  # S3: FR-TIC-06 row readout (SupportTeam.name)
    assignee_name: str | None  # S3: assignee User.full_name
    needs_reassignment: bool  # S3: FR-ASG-09 derived flag
```

- `TicketDetail` — add the same three fields after `assigned_to`:

```python
    assigned_to: str | None
    team_name: str | None
    assignee_name: str | None
    needs_reassignment: bool
```

- [ ] **Step 2: Enrich `list_tickets` (add `team_id` filter + names + flag)**

In `backend/app/services/ticket_service.py`:

Extend the import added in Task 2 so both predicates are available:

```python
from app.services.assignment import is_valid_assignee, needs_reassignment
```

Change the `list_tickets` signature (keyword-only `team_id` with a default keeps every existing caller working) — the current signature/body (lines ~141-166) is:

```python
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
```

Replace it with (adds the `team_id` param + its filter block and routes rows through `_attach_meta`):

```python
async def list_tickets(session: AsyncSession, *, user: User, page: int, page_size: int,
                       status: str | None = None, q: str | None = None, assigned_to_me: bool = False,
                       team_id: str | None = None):
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
    if team_id:
        try:
            tid = uuid.UUID(str(team_id))
        except ValueError:
            raise AppError(422, "VALIDATION_ERROR", "team_id không hợp lệ.")
        # Scope-safe (Controller decision 4): combined with _scope_conds this can
        # only ever return rows the caller may already see.
        conds.append(Ticket.team_id == tid)
    total = int((await session.execute(select(func.count(Ticket.id)).where(*conds))).scalar_one())
    stmt = (
        select(*_ITEM_COLS)
        .where(*conds)
        .order_by(Ticket.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).mappings().all()
    items = [_row_to_item(r) for r in rows]
    return total, await _attach_meta(session, items)
```

Add a module-level helper `_attach_meta` (batch name + flag resolution; no ORM relationship added, so alembic stays clean):

```python
async def _attach_meta(session: AsyncSession, items: list[dict]) -> list[dict]:
    """Attach team_name / assignee_name / needs_reassignment to list dicts.

    The page is small (<=100) so two batched lookups are enough; the derived flag
    (FR-ASG-09) reads the assignee's is_active at read time (Controller decision 1).
    """
    if not items:
        return items
    team_ids = {uuid.UUID(i["team_id"]) for i in items if i["team_id"]}
    assignee_ids = {uuid.UUID(i["assigned_to"]) for i in items if i["assigned_to"]}
    team_names: dict[str, str] = {}
    if team_ids:
        team_names = {str(i): n for i, n in (
            await session.execute(select(SupportTeam.id, SupportTeam.name)
                                  .where(SupportTeam.id.in_(team_ids)))).all()}
    assignee_meta: dict[str, tuple[str, bool]] = {}
    if assignee_ids:
        assignee_meta = {str(i): (name, active) for i, name, active in (
            await session.execute(select(User.id, User.full_name, User.is_active)
                                  .where(User.id.in_(assignee_ids)))).all()}
    for it in items:
        uid = it["assigned_to"]
        name, active = assignee_meta.get(uid, (None, None)) if uid else (None, None)
        it["team_name"] = team_names.get(it["team_id"]) if it["team_id"] else None
        it["assignee_name"] = name
        it["needs_reassignment"] = needs_reassignment(
            assigned_to=bool(uid), status=it["status"], assignee_active=active)
    return items
```

- [ ] **Step 3: Enrich the detail mapper + add the list query param + /teams member fields**

In `backend/app/api/tickets.py`:

Add two imports — `SupportTeam` next to the existing model imports (`from app.models.ticket import Attachment, Ticket`), and the pure predicate from Task 1 so the detail flag uses the SAME code path as the list (single source of truth, no duplicated logic):

```python
from app.models.team import SupportTeam
from app.services.assignment import needs_reassignment
```

`User` and `session` are already available; `app.services.assignment.needs_reassignment` is the pure predicate unit-tested in Task 1.

Inside `_to_detail`, resolve team/assignee names + the derived flag before building the response. Insert this block right after `history = sorted(ticket.history, key=lambda h: h.created_at, reverse=True)` (the current mapper at lines 75-107):

```python
    # S3 readouts: team/assignee names + FR-ASG-09 needs_reassignment (derived at
    # read time from the assignee's is_active — Controller decision 1).
    team_name = assignee_name = None
    assignee_active = None
    if ticket.team_id is not None:
        team = await session.get(SupportTeam, ticket.team_id)
        team_name = team.name if team is not None else None
    if ticket.assigned_to is not None:
        assignee = await session.get(User, ticket.assigned_to)
        if assignee is not None:
            assignee_name = assignee.full_name
            assignee_active = assignee.is_active
    flag_needs_reassignment = needs_reassignment(
        assigned_to=ticket.assigned_to is not None,
        status=ticket.status,
        assignee_active=assignee_active,
    )
```

Then add the three fields to the returned `TicketDetail(...)` right after `team_id=_s(ticket.team_id), assigned_to=_s(ticket.assigned_to),`:

```python
        team_name=team_name, assignee_name=assignee_name, needs_reassignment=flag_needs_reassignment,
```

On the list route, add the query param and pass it through:

```python
    team_id: str | None = Query(default=None),
```

```python
    total, items = await ticket_service.list_tickets(
        session, user=user, page=page, page_size=page_size, status=status, q=q,
        assigned_to_me=assigned_to_me, team_id=team_id,
    )
```

On `/teams`, map the two new member fields (replacing the current `TeamMemberOut(...)` line):

```python
            TeamMemberOut(id=str(m.user.id), full_name=m.user.full_name, team_role=m.team_role,
                          role=m.user.role, is_active=m.user.is_active)
```

(`m.user` is already eager-loaded by `teams_with_members`, so reading `m.user.role`/`m.user.is_active` is sync-safe.)

- [ ] **Step 4: Write the failing HTTP tests**

Append to `backend/tests/integration/test_http_tickets.py`. Reuse that module's existing helpers verbatim: `_tag`, `_add_user`, `_create_org` (returns `team_a` managed by `manager` with `agent_a` inside, `team_b` with `agent_b`, and an `admin`), `_token(user)`, `_cleanup_org(org, ticket_ids)`, `_public_create(client, **data)`, plus the module imports (`User`, `TeamMember`, `TeamRole`, `UserRole`, `ticket_service`, `AsyncSessionLocal`). Ticket ids come from the public-create response via a `track_public` lookup, exactly as the existing `test_assign_scope_and_listing` does. Append these four tests:

```python
async def test_list_detail_show_team_assignee_and_needs_reassignment(client):
    org = await _create_org()
    mgr_tok = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {mgr_tok}"}
    try:
        r = await _public_create(client, requester_name="Khách S3", requester_email="khach.s3@example.com",
                                 subject="Cần gán cho team A", description="Mô tả đủ dài cho vé phân công S3.")
        code = r.json()["ticket_code"]
        async with AsyncSessionLocal() as s:
            t = await ticket_service.track_public(s, email="khach.s3@example.com", ticket_code=code)
            ticket_id = t.id
        assign = await client.post(
            f"/api/tickets/{ticket_id}/assign", headers=headers,
            json={"team_id": str(org["team_a"].id), "assigned_to": str(org["agent_a"].id),
                  "version": 1},
        )
        assert assign.status_code == 200, assign.text
        assert assign.json()["team_name"] == org["team_a"].name
        assert assign.json()["assignee_name"] == org["agent_a"].full_name
        assert assign.json()["needs_reassignment"] is False
        detail = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["team_name"] == org["team_a"].name
        assert detail.json()["assignee_name"] == org["agent_a"].full_name
        assert detail.json()["needs_reassignment"] is False
        # Manager list row carries the same readouts (FR-TIC-06 column).
        lst = await client.get("/api/tickets", headers=headers)
        row = next(i for i in lst.json()["items"] if i["id"] == str(ticket_id))
        assert row["team_name"] == org["team_a"].name
        assert row["assignee_name"] == org["agent_a"].full_name
        assert row["needs_reassignment"] is False
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_needs_reassignment_flag_tracks_assignee_deactivation(client):
    org = await _create_org()
    agent_c = await _add_user(f"agc.{_tag()}@example.com", "Agent C HTTP", UserRole.AGENT.value)
    org["user_ids"].append(agent_c.id)  # _cleanup_org now owns agent_c too
    mgr_tok = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {mgr_tok}"}
    try:
        r = await _public_create(client, requester_name="Khách S3 B", requester_email="khach.s3b@example.com",
                                 subject="Theo dõi cờ cần phân công lại", description="Mô tả đủ dài cho vé theo dõi cờ S3.")
        code = r.json()["ticket_code"]
        async with AsyncSessionLocal() as s:
            t = await ticket_service.track_public(s, email="khach.s3b@example.com", ticket_code=code)
            ticket_id = t.id
        assign = await client.post(
            f"/api/tickets/{ticket_id}/assign", headers=headers,
            json={"team_id": str(org["team_a"].id), "assigned_to": str(org["agent_a"].id), "version": 1})
        assert assign.status_code == 200, assign.text
        # Deactivate the assignee's *user* row directly (S6 owns the endpoint; S3
        # derives the flag, so a DB-level toggle is the honest trigger).
        async with AsyncSessionLocal() as s:
            u = await s.get(User, org["agent_a"].id)
            u.is_active = False
            await s.commit()
        detail = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["needs_reassignment"] is True
        # Reassign to a still-active AGENT of the same team -> flag clears.
        async with AsyncSessionLocal() as s:
            s.add(TeamMember(team_id=org["team_a"].id, user_id=agent_c.id,
                             team_role=TeamRole.MEMBER.value, is_active=True))
            await s.commit()
        v2 = detail.json()["version"]
        reassign = await client.post(
            f"/api/tickets/{ticket_id}/assign", headers=headers,
            json={"team_id": str(org["team_a"].id), "assigned_to": str(agent_c.id), "version": v2})
        assert reassign.status_code == 200, reassign.text
        assert reassign.json()["assignee_name"] == "Agent C HTTP"
        assert reassign.json()["needs_reassignment"] is False
        # List row shows the cleared flag too.
        lst = await client.get("/api/tickets", headers=headers)
        row = next(i for i in lst.json()["items"] if i["id"] == str(ticket_id))
        assert row["needs_reassignment"] is False
        # Deactivating the NEW assignee re-flags the SAME ticket in the list.
        async with AsyncSessionLocal() as s:
            u = await s.get(User, agent_c.id)
            u.is_active = False
            await s.commit()
        lst2 = await client.get("/api/tickets", headers=headers)
        row2 = next(i for i in lst2.json()["items"] if i["id"] == str(ticket_id))
        assert row2["needs_reassignment"] is True
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_list_team_filter_scoped(client):
    org = await _create_org()
    mgr_tok = await _token(org["manager"])
    adm_tok = await _token(org["admin"])
    mgr_h = {"Authorization": f"Bearer {mgr_tok}"}
    adm_h = {"Authorization": f"Bearer {adm_tok}"}
    try:
        r1 = await _public_create(client, requester_name="Khách S3 C", requester_email="khach.s3c@example.com",
                                  subject="Vé team A", description="Mô tả đủ dài cho vé team A của S3.")
        async with AsyncSessionLocal() as s:
            t1 = await ticket_service.track_public(s, email="khach.s3c@example.com", ticket_code=r1.json()["ticket_code"])
            id_a = t1.id
        r2 = await _public_create(client, requester_name="Khách S3 D", requester_email="khach.s3d@example.com",
                                  subject="Vé team B", description="Mô tả đủ dài cho vé team B của S3.")
        async with AsyncSessionLocal() as s:
            t2 = await ticket_service.track_public(s, email="khach.s3d@example.com", ticket_code=r2.json()["ticket_code"])
            id_b = t2.id
        a = await client.post(f"/api/tickets/{id_a}/assign", headers=mgr_h,
                              json={"team_id": str(org["team_a"].id), "assigned_to": str(org["agent_a"].id), "version": 1})
        assert a.status_code == 200, a.text
        b = await client.post(f"/api/tickets/{id_b}/assign", headers=adm_h,
                              json={"team_id": str(org["team_b"].id), "assigned_to": str(org["agent_b"].id), "version": 1})
        assert b.status_code == 200, b.text
        # Scope-safe filter (Controller decision 4): manager filtering to team A
        # gets id_a, never id_b (id_b sits in a team the manager does not manage).
        lst = await client.get(f"/api/tickets?team_id={org['team_a'].id}", headers=mgr_h)
        ids = [i["id"] for i in lst.json()["items"]]
        assert str(id_a) in ids and str(id_b) not in ids
        # Admin sees the ticket under the same filter primitive.
        lst_all = await client.get(f"/api/tickets?team_id={org['team_a'].id}", headers=adm_h)
        ids_all = [i["id"] for i in lst_all.json()["items"]]
        assert str(id_a) in ids_all
    finally:
        await _cleanup_org(org, [id_a, id_b])


async def test_teams_members_carry_role_and_is_active(client):
    org = await _create_org()
    mgr_tok = await _token(org["manager"])
    try:
        r = await client.get("/api/teams", headers={"Authorization": f"Bearer {mgr_tok}"})
        assert r.status_code == 200, r.text
        teams = r.json()
        assert len(teams) == 1 and teams[0]["id"] == str(org["team_a"].id)
        by_id = {m["id"]: m for m in teams[0]["members"]}
        assert by_id[str(org["manager"].id)]["team_role"] == "MANAGER"
        assert by_id[str(org["manager"].id)]["role"] == "MANAGER"
        assert by_id[str(org["agent_a"].id)]["role"] == "AGENT"
        assert by_id[str(org["agent_a"].id)]["is_active"] is True
    finally:
        await _cleanup_org(org, [])
```

- [ ] **Step 5: Implement the read-side changes until the new tests pass**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_http_tickets.py -q`
Expected: all existing (5) + new (4) tests pass — **9 passed**.

- [ ] **Step 6: Regression — full backend suites + alembic drift**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: **56 passed** (unchanged — no new unit tests this task; the pure predicates were Task 1's).

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q`
Expected: **23 passed** (S1 auth 4 + S2 12 + Task 2's 3 + this task's 4).

Run: `docker compose exec backend alembic check`
Expected: `No new upgrade operations detected.` — the ONLY model-adjacent change is a pure-Python addition of a `TicketDetail`/`TicketListItem`/`TeamMemberOut` pydantic field set, no SQLAlchemy column, so autogenerate stays quiet.

- [ ] **Step 7: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add backend/app/schemas/ticket.py backend/app/services/ticket_service.py backend/app/api/tickets.py backend/tests/integration/test_http_tickets.py
git commit -m "feat(backend): S3 list/detail team+assignee readouts, derived needs_reassignment, team_id filter, /teams member role+is_active
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frontend — assignment readout, needs-reassignment banner, picker guard, list column + team filter

**Why one task:** the FE is the demo surface for FR-ASG-07/08/09 + FR-TIC-06. Consumes the Task 3 contract (three new detail/list fields + member `role`/`is_active`).

**Files:**
- Modify: `frontend/src/pages/TicketDetailPage.jsx`
- Modify: `frontend/src/pages/TicketsListPage.jsx`
- Modify: `frontend/src/styles/tickets.css` (only if a new visual state needs it)

**Interfaces:**
- Consumes: `detail.team_name`, `detail.assignee_name`, `detail.needs_reassignment`; list-item `team_name`, `assignee_name`, `needs_reassignment`; `/api/teams` members `role` + `is_active`; existing `useAuth().user.role`, `api.get`, `api.post`. Existing CSS tokens/badges.

- [ ] **Step 1: Detail page — assignment readout + banner + picker guard**

In `frontend/src/pages/TicketDetailPage.jsx`, inside the `<header className="ticket-head">` block, add an assignment readout line under the existing requester/time `<p>` (after line ~275 `{detail.requester_name} · {detail.requester_email} · Gửi lúc ...`):

```jsx
        <p className="text-muted">
          Nhóm: {detail.team_name || '—'} · Người phụ trách: {detail.assignee_name || 'Chưa phân công'}
        </p>
        {detail.needs_reassignment && (
          <p className="form-error needs-reassign" role="alert">
            Vé này cần được phân công lại — người phụ trách hiện tại đã bị vô hiệu hóa.
            {canAssign && (
              <button className="btn-secondary" type="button" onClick={openAssign}>Phân công lại</button>
            )}
          </p>
        )}
```

The banner shows for every staff role who can see the detail (it is scoped data); the "Phân công lại" CTA inside it is gated to `canAssign` (MANAGER/ADMIN) — an AGENT who can view the ticket sees the banner but no CTA, matching the route-level role gate. Do NOT add a second CTA to the action row (the existing `Phân công` button at line ~285 already sits there).

In the assignee `<select>` options (currently ~lines 428-431), disable any member who is not an active AGENT, and keep them visible with a hint:

```jsx
                {(currentTeam?.members || []).map((m) => {
                  const blocked = m.role !== 'AGENT' || m.is_active === false;
                  return (
                    <option key={m.id} value={String(m.id)} disabled={blocked}>
                      {m.full_name} ({m.team_role}){blocked ? ' — không gán được' : ''}
                    </option>
                  );
                })}
```

`submitAssign` already resets `assigneeId` when the team changes, so a blocked member can never be submitted through the picker (the backend Task 2 guard is the backstop).

- [ ] **Step 2: Detail page — reopening assign on a needs-reassignment ticket**

`openAssign` already loads `/api/teams` once and preserves the current assignee when it is still a member of the preferred team. For a needs-reassignment ticket the current assignee is deactivated and will now render as a *disabled* option — the desired visual (the manager sees why the flag is on). No code change required for correctness.

- [ ] **Step 3: List page — team/assignee column, needs-reassignment badge, team filter**

In `frontend/src/pages/TicketsListPage.jsx` (current layout: imports at lines 1-7; filter states at lines 19-22; `load(nextPage, filters)` at lines 24-47; the reload `useEffect` at lines 49-52; the filter `<form>` at lines 69-89 with the status `<select>` ending at line 83; header `<th>Khách hàng</th>` at line 105; requester `<td>` at line 114):

1. Add the auth import after line 3 (`import { api } from '../api/client.js';`):

```jsx
import { useAuth } from '../auth/AuthContext.jsx';
```

2. Add `user`, the teams state and the filter state right after line 22 (`const [submittedQ, setSubmittedQ] = useState('');`):

```jsx
  const { user } = useAuth();
  const canFilterTeam = user?.role === 'MANAGER' || user?.role === 'ADMIN';
  const [teams, setTeams] = useState([]);
  const [teamFilter, setTeamFilter] = useState('');
```

3. Load teams once on mount when the caller may filter (a new `useEffect` right after the existing reload `useEffect` at lines 49-52):

```jsx
  useEffect(() => {
    if (!canFilterTeam) return;
    api.get('/api/teams').then(setTeams).catch(() => setTeams([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canFilterTeam]);
```

4. In `load(nextPage, filters)` read `teamFilter` exactly like the other filters and send it only when set — insert right after line 37 (`if (mine) params.set('assigned_to_me', 'true');`):

```jsx
      const tf = filters.teamFilter ?? teamFilter;
      if (tf) params.set('team_id', tf);
```

5. Add `teamFilter` to the reload `useEffect` (lines 49-52) so changing it refetches from page 1:

```jsx
  useEffect(() => {
    load(1, { status, q: submittedQ, assignedToMe, teamFilter });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, submittedQ, assignedToMe, teamFilter]);
```

6. In the filter `<form>`, add the team `<select>` right after the status `<select>` (after line 83) and before the "Vé của tôi" label:

```jsx
        {canFilterTeam && (
          <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} aria-label="Lọc theo nhóm">
            <option value="">Tất cả nhóm</option>
            {teams.map((t) => <option key={t.id} value={String(t.id)}>{t.name}</option>)}
          </select>
        )}
```

7. Add a `<th>Nhóm / Phụ trách</th>` to the header row right after `<th>Khách hàng</th>` (line 105), and add the readout cell to each row right after the requester `<td>` (line 114):

```jsx
                    <td>
                      {t.team_name || '—'}
                      {t.team_name && t.assignee_name ? ' · ' : ''}
                      {t.assignee_name || (t.team_name ? 'Chưa phân công' : '')}
                      {t.needs_reassignment && <span className="badge badge--pending">Cần phân công lại</span>}
                    </td>
```

(The badge reuses the existing pending style. If the readout column needs emphasis beyond the badge, add a `needs-reassign-cell` class in Step 4.)

- [ ] **Step 4: CSS (only if a state needs it)**

In `frontend/src/styles/tickets.css`, add a minimal rule ONLY if the banner/cell need emphasis beyond existing `.form-error`/`.badge`:

```css
/* S3: ticket whose assignee is deactivated (FR-ASG-09) */
.needs-reassign { display: flex; align-items: center; gap: var(--space-2); }
.needs-reassign-cell { font-weight: 600; }
```

Skip this step if you can express the states with existing tokens/classes.

- [ ] **Step 5: Build + visual/behavioral verification**

Run: `cd "D:/DuAm/HeThongHoTroAI/frontend" && npm run build`
Expected: production build succeeds with no import/JSX errors.

Run the FE dev server or the rebuilt static bundle and verify by hand (the acceptance gate in Task 5 walks the full §10 S3 demo): a manager opening a ticket sees "Nhóm: Team Kỹ thuật · Người phụ trách: Trần Thị Lan"; a disabled-assignee ticket shows the needs-reassignment banner; the list shows the new column and team filter; the assignee picker greys out non-AGENT/inactive members. (This task's "verify" is the build + the §10 demo walk in Task 5; a unit harness for React is out of scope per the design spec §11.)

- [ ] **Step 6: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add frontend/src/pages/TicketDetailPage.jsx frontend/src/pages/TicketsListPage.jsx frontend/src/styles/tickets.css
git commit -m "feat(frontend): S3 assignment readout, needs-reassignment banner, guarded assignee picker, list team column + filter
Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Acceptance over the running stack + README S3 block

**Why one task:** the S3 slice's acceptance gate — clean tree, backend restart + frontend rebuild so S3 is live, alembic check still clean, all unit + integration suites green, then a live HTTP §10 S3 demo (assign → agent sees; reassign keeps history; cross-team 403; needs-reassignment flag), and a README S3 block so a partner can replay it.

**Files:**
- Modify: `README.md` (S3 block after the S2 block)
- No code files change in this task.

**Interfaces:** consumes Tasks 1-4 code + tests + the running demo stack (db `:5433` / backend `:8001` / frontend `:8080`).

- [ ] **Step 1: Confirm a clean tree**

Run: `cd "D:/DuAm/HeThongHoTroAI" && git status --short`
Expected: clean (only Tasks 1-4 commits on top of S2 HEAD `7902f81`).

- [ ] **Step 2: Reload S3 onto the running stack**

S3 adds no dependency and no migration — the backend container bind-mounts `./backend:/app` and runs uvicorn WITHOUT `--reload`, so a restart re-imports the fresh code. The frontend is a static nginx build → rebuild its image.

Run: `cd "D:/DuAm/HeThongHoTroAI" && docker compose restart backend`
Run: `cd "D:/DuAm/HeThongHoTroAI" && docker compose up -d --build frontend`
Expected: `backend` restarted (seed idempotent, alembic no-op), `frontend` recreated. Wait for readiness:

Run: `powershell -Command "1..60 | ForEach-Object { try { $r = Invoke-RestMethod http://localhost:8001/api/health/ready; if ($r.status -eq 'ok') { 'READY'; break } } catch {}; Start-Sleep -Milliseconds 1000 }"`
Expected: prints `READY`.

Confirm no migration drift:
Run: `docker compose exec backend alembic check`
Expected: `No new upgrade operations detected.` (Global Constraint: no migration in S3).

- [ ] **Step 3: Run the unit suite**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && .venv/Scripts/python -m pytest tests/unit -q`
Expected: **56 passed** (S1 35 + S2 16 + S3 Task 1's 5).

- [ ] **Step 4: Run the integration suites (compose DB on :5433)**

Run: `cd "D:/DuAm/HeThongHoTroAI/backend" && INTEGRATION=1 DATABASE_URL="postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support" RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration -q`
Expected: all integration tests pass — S1 `test_auth.py`, S2 `test_ticket_service.py` (7) + `test_http_tickets.py` (5) + `test_seed.py`, plus S3's service (3) + HTTP (4) additions = **23**. Report the exact pass count and the per-file inventory (`pytest --collect-only` gives the authoritative split); reconcile any arithmetic slip in the report, not silently.

- [ ] **Step 5: Live HTTP smoke — the §10 S3 demo end to end**

Walk the demo against the running backend (:8001) using the seeded identities (hung.manager manages **Team Kỹ thuật**, which contains lan.agent + minh.agent). PowerShell `curl.exe` is expected on the host; read raw JSON and copy ids manually if `jq` is absent.

5a. Public create a fresh ticket (existing S2 flow), then note its id + version:

```powershell
curl.exe -s -X POST http://localhost:8001/api/public/tickets `
  -F "requester_name=Khách Hàng S3" `
  -F "requester_email=khach.s3demo@example.com" `
  -F "subject=Không truy cập được VPN sau cập nhật" `
  -F "description=Máy báo lỗi xác thực kể từ bản cập nhật hôm nay." `
  -F "category=TECHNICAL"
```

5b. Manager login + teams picker shows **Team Kỹ thuật** with member `role`/`is_active`:

```powershell
$MGR = (curl.exe -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" `
  -d '{"email":"hung.manager@example.com","password":"hung.manager@Dev123"}') | ConvertFrom-Json
curl.exe -s http://localhost:8001/api/teams -H "Authorization: Bearer $($MGR.access_token)"
```

Expected: **Team Kỹ thuật** returned; its members each carry `id`, `full_name`, `team_role`, `role`, `is_active` (lan.agent → `role:"AGENT"`, `is_active:true`; hung.manager also appears with `role:"MANAGER"`). Capture `teamId`, `lanId`, and `minhId`.

5c. Assign to lan.agent → detail returns `team_name`/`assignee_name`/`needs_reassignment:false`:

```powershell
curl.exe -s "http://localhost:8001/api/tickets?q=TK-XXXXXXXX" -H "Authorization: Bearer $($MGR.access_token)"
curl.exe -s -X POST "http://localhost:8001/api/tickets/{ticketId}/assign" `
  -H "Authorization: Bearer $($MGR.access_token)" -H "Content-Type: application/json" `
  -d "{\"team_id\":\"{teamId}\",\"assigned_to\":\"{lanId}\",\"reason\":\"Phân công cho đội Kỹ thuật\",\"version\":{version}}"
```

Expected: `200`; body has `"team_name":"Team Kỹ thuật"`, `"assignee_name":"Trần Thị Lan"`, `"needs_reassignment":false`.

5d. Agent lan sees the assigned ticket in her scoped list:

```powershell
$AGT = (curl.exe -s -X POST http://localhost:8001/api/auth/login -H "Content-Type: application/json" `
  -d '{"email":"lan.agent@example.com","password":"lan.agent@Dev123"}') | ConvertFrom-Json
curl.exe -s "http://localhost:8001/api/tickets?assigned_to_me=true" -H "Authorization: Bearer $($AGT.access_token)"
```

Expected: the list item includes the ticket with `team_name:"Team Kỹ thuật"` and `assignee_name:"Trần Thị Lan"`.

5e. Manager reassigns to minh.agent → detail history shows TWO `ASSIGNED` rows (Lan → Minh, FR-ASG-08):

```powershell
$D = (curl.exe -s -X POST "http://localhost:8001/api/tickets/{ticketId}/assign" `
  -H "Authorization: Bearer $($MGR.access_token)" -H "Content-Type: application/json" `
  -d "{\"team_id\":\"{teamId}\",\"assigned_to\":\"{minhId}\",\"reason\":\"Đổi người phụ trách\",\"version\":{newVersion}}") | ConvertFrom-Json
# inspect $D.history for event_type == ASSIGNED entries
```

Expected: two `ASSIGNED` history rows, `old_value.assigned_to` of the second == lanId and `new_value.assigned_to` == minhId; `needs_reassignment` still `false`.

5f. Manager tries a cross-team assignment into the team he does not manage → 403:

```powershell
$OTHER = (curl.exe -s http://localhost:8001/api/teams -H "Authorization: Bearer $($MGR.access_token)")
# pick the id of Team Tài khoản & Thanh toán from $OTHER
curl.exe -s -o NUL -w "%{http_code}" -X POST "http://localhost:8001/api/tickets/{ticketId}/assign" `
  -H "Authorization: Bearer $($MGR.access_token)" -H "Content-Type: application/json" `
  -d "{\"team_id\":\"{otherTeamId}\",\"assigned_to\":null,\"version\":{newVersion}}"
```

Expected: `403` (ACCESS_DENIED — "Bạn chỉ có thể gán vé vào nhóm mình quản lý.").

5g. Needs-reassignment flag (FR-ASG-09), DB-toggled because admin user deactivation ships in S6 — this is a manual DB step to make the derived flag visible, then restore:

```powershell
docker compose exec -T db psql -U ai_support -d ai_support -c "UPDATE users SET is_active = false WHERE email = 'minh.agent@example.com';"
# GET the ticket detail as manager -> needs_reassignment true
curl.exe -s "http://localhost:8001/api/tickets/{ticketId}" -H "Authorization: Bearer $($MGR.access_token)"
# reassign back to lan.agent (active) -> flag clears, history has THREE ASSIGNED rows
docker compose exec -T db psql -U ai_support -d ai_support -c "UPDATE users SET is_active = true WHERE email = 'minh.agent@example.com';"
```

Expected: after step 1 the detail shows `"needs_reassignment":true`; after reassigning to lan.agent it is `false` and a third `ASSIGNED` history row exists. **Restore `minh.agent` to `is_active=true` immediately** — a leftover deactivated seed user would confuse later slices.

> The ticket created in 5a persists as intended S2/S3 demo data. Leave it; it carries a clean reassignment history that doubles as the FR-ASG-08 evidence.

5h. Browser pass (recommended): open http://localhost:8080 → login as `hung.manager@example.com` → `/app/tickets` shows the new "Nhóm / Phụ trách" column + team filter → open the demo ticket → header shows "Nhóm: Team Kỹ thuật · Người phụ trách: …" → "Phân công" dialog greys out non-AGENT/inactive members → reassign and watch the timeline gain an "ASSIGNED" event. If you left `minh.agent` inactive while testing the banner, you will see the needs-reassignment CTA — restore him before finishing.

- [ ] **Step 6: Document the slice in the README**

Edit `README.md` — insert this block after the S2 block (the S2 block ends with its own "Chi tiết kỹ thuật:" line):

```markdown
### S3 — Nhóm & phân công

Luồng phân công được làm đầy trên nền tối thiểu của S2 (FR-ASG):

- **Người được gán phải hợp lệ**: khi gán cho một người, người đó phải là **Support Agent đang hoạt động** thuộc nhóm được chọn (`role=AGENT`, chưa bị vô hiệu hóa, còn trong nhóm). Gán sai → `400 ASSIGNEE_NOT_IN_TEAM`.
- **Phạm vi phân công**: Quản lý chỉ gán trong nhóm mình quản lý; Admin gán được toàn hệ thống; Nhân viên không được gán. Vé gán ngoài nhóm của Quản lý → `403`. Phân công **không** làm đổi trạng thái/`resolved_at` (FR-ASG-10).
- **Đổi người phụ trách**: mỗi lần gán/đổi đều ghi một dòng lịch sử `ASSIGNED` (ai gán, ai/nhóm nhận, lúc nào, lý do), giữ nguyên quá khứ (FR-ASG-07/08).
- **"Cần phân công lại"** (FR-ASG-09): nếu người phụ trách của một vé đang mở bị **vô hiệu hóa**, vé hiển thị cờ *cần phân công lại* ở danh sách + chi tiết. Cờ được **tính động** (dựa trên trạng thái người phụ trách), tự hết khi gán cho một agent đang hoạt động.
- Danh sách/detail hiển thị **tên nhóm + người phụ trách**; danh sách thêm bộ lọc **theo nhóm** (Quản lý/Admin) trong phạm vi được xem.

Demo nhanh: đăng nhập `hung.manager@example.com` (mật khẩu seed ở bảng S1) → mở vé trong `/app/tickets` → "Phân công" → chọn nhóm + agent → xem lịch sử trong "Hoạt động" → thử gán sang nhóm khác để thấy `403`. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s3-teams-assignment.md`.
```

- [ ] **Step 7: Commit**

```bash
cd "D:/DuAm/HeThongHoTroAI"
git add README.md
git commit -m "docs(s3): acceptance gates green, README S3 demo block

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-review (writing-plans checklist, run by the plan author)

**1. Spec coverage.** Design spec §10 S3 + SRS §4.4 FR-ASG-01..10 mapped:
- FR-ASG-01 (assign a valid team) — S2 already; Task 3 readout. ✔
- FR-ASG-02/03 (assign a valid Support Agent; assignee ∈ team & active) — Task 2 (role + user-active + membership-active). ✔
- FR-ASG-04 (Manager only own teams) — S2 enforced; Task 5 step 5f demo. ✔
- FR-ASG-05 (Admin global) — S2 enforced; Task 2 tests use admin cross-team. ✔
- FR-ASG-06 (Agent cannot assign to others) — route gate MANAGER_ADMIN unchanged; Task 5 browser pass. ✔
- FR-ASG-07 (record actor/recipient/time/reason) — S2 `ASSIGNED` history + audit; Task 2 pins snapshot. ✔
- FR-ASG-08 (reassign + full history) — Task 2 test (2 ASSIGNED rows) + Task 5 step 5e. ✔
- FR-ASG-09 (needs reassignment when assignee deactivated) — derived flag, Tasks 1/3/4/5. ✔
- FR-ASG-10 (assign does not auto-resolve/close) — Task 2 test on a RESOLVED ticket. ✔
- FR-TIC-06 row shows team/assignee — Task 3 list readout + Task 4 column. ✔
- Design-spec §10 S3 "dialog assign UI / scoping danh sách theo nhóm / lịch sử phân công" — Task 4 (picker guard + readout + banner), Task 3 team filter. ✔

**2. Placeholder scan.** All test bodies are verbatim against the real module helpers (`_create_org`, `_token`, `_add_user`, `_cleanup_org`, `_public_create`, `track_public` lookup idiom) — the plan author read both integration modules before finalizing, so no "adjust to the module's builders" stubs remain. Two implementation notes that are real, not TBD, are called out inline: Task 2 Step 3's exact before/after for `assign_ticket`, and Task 3 Step 3's single committed router approach (import the pure predicate — no duplicated logic). No code is left as "similar to Task N"; changed regions are quoted with anchors. No `TBD`/`TODO` remains that a task could run without resolving.

**3. Type/name consistency.** `needs_reassignment`, `team_name`, `assignee_name` appear identically on `TicketListItem`/`TicketDetail` (Task 3) and are consumed by that spelling in Task 4's JSX. `role` + `is_active` on `TeamMemberOut` (Task 3) are consumed as `m.role`/`m.is_active` in Task 4. `is_valid_assignee`, `needs_reassignment`, `is_open_status` from `assignment.py` (Task 1) are imported under those exact names in Task 2/3. The `assign_ticket` signature is unchanged so S2 callers/tests keep compiling. Counts stay monotonic and the Task 5 totals are explicitly "recomputed at acceptance" to avoid the S1/S2 arithmetic-slip pattern.

---

*Plan ends. Execution starts at Task 1 when the mode is chosen (Task 5 is the acceptance gate; do not reorder).*
