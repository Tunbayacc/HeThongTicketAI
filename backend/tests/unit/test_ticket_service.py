"""Unit tests for app.services.ticket_service.

Verifies ticket scoping, portal creation, update, status transitions, and assignment
without a live PostgreSQL database.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.errors import AppError
from app.models.enums import AuditOutcome, TicketStatus, UserRole
from app.models.team import SupportTeam
from app.models.ticket import SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services import ticket_service
from app.services.storage import StoredFile

_NOW = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)


class _MockResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        mock = MagicMock()
        mock.all.return_value = self._scalars_list
        mock.__iter__.return_value = iter(self._scalars_list)
        return mock


def _make_mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_ticket(
    *,
    ticket_id=None,
    ticket_code="TK-TEST001",
    status="OPEN",
    priority="MEDIUM",
    category="TECHNICAL",
    version=1,
    team_id=None,
    assigned_to=None,
    sla_policy_id=None,
    first_response_due_at=None,
    resolution_due_at=None,
) -> Ticket:
    t = Ticket(
        id=ticket_id or uuid.uuid4(),
        ticket_code=ticket_code,
        requester_name="Nguyen Van A",
        requester_email="customer@example.com",
        subject="Khong dang nhap duoc",
        description="Moi lan dang nhap deu bao loi sai mat khau.",
        status=status,
        priority=priority,
        category=category,
        version=version,
        team_id=team_id,
        assigned_to=assigned_to,
        sla_policy_id=sla_policy_id,
        first_response_due_at=first_response_due_at,
        resolution_due_at=resolution_due_at,
    )
    t.history = []
    t.comments = []
    t.attachments = []
    return t


def _make_user(*, user_id=None, role=UserRole.AGENT.value, is_active=True) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        email="staff@example.com",
        full_name="Staff User",
        role=role,
        is_active=is_active,
        password_hash="dummy",
    )


# ---- Scope and View checks ----


def test_can_view_admin_can_view_any_ticket():
    admin = _make_user(role=UserRole.ADMIN.value)
    ticket = _make_ticket()
    assert ticket_service._can_view(admin, ticket, view_ids=None) is True


def test_can_view_agent_can_view_if_assigned_or_member_team():
    agent = _make_user(role=UserRole.AGENT.value)
    my_team_id = uuid.uuid4()
    other_team_id = uuid.uuid4()

    # Case 1: Assigned to agent
    t1 = _make_ticket(assigned_to=agent.id, team_id=other_team_id)
    assert ticket_service._can_view(agent, t1, view_ids=[my_team_id]) is True

    # Case 2: In agent's team
    t2 = _make_ticket(assigned_to=None, team_id=my_team_id)
    assert ticket_service._can_view(agent, t2, view_ids=[my_team_id]) is True

    # Case 3: Neither assigned nor in team -> False
    t3 = _make_ticket(assigned_to=uuid.uuid4(), team_id=other_team_id)
    assert ticket_service._can_view(agent, t3, view_ids=[my_team_id]) is False

    # Case 4: Unassigned ticket without team -> Agent cannot view
    t4 = _make_ticket(assigned_to=None, team_id=None)
    assert ticket_service._can_view(agent, t4, view_ids=[my_team_id]) is False


def test_can_view_manager_can_view_unassigned_pool_and_managed_teams():
    manager = _make_user(role=UserRole.MANAGER.value)
    team_id = uuid.uuid4()
    other_team_id = uuid.uuid4()

    # Case 1: Unassigned ticket (team_id is None) -> Manager can view (intake pool)
    t1 = _make_ticket(assigned_to=None, team_id=None)
    assert ticket_service._can_view(manager, t1, view_ids=[team_id]) is True

    # Case 2: In managed team
    t2 = _make_ticket(assigned_to=None, team_id=team_id)
    assert ticket_service._can_view(manager, t2, view_ids=[team_id]) is True

    # Case 3: Other team not managed -> False
    t3 = _make_ticket(assigned_to=None, team_id=other_team_id)
    assert ticket_service._can_view(manager, t3, view_ids=[team_id]) is False


@pytest.mark.asyncio
async def test_get_scoped_ticket_invalid_uuid_raises_404():
    session = _make_mock_session()
    user = _make_user()
    with pytest.raises(AppError) as exc_info:
        await ticket_service.get_scoped_ticket(session, user=user, ticket_id="not-a-uuid")
    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "TICKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_scoped_ticket_out_of_scope_raises_404_anti_leak():
    session = _make_mock_session()
    agent = _make_user(role=UserRole.AGENT.value)
    other_team = uuid.uuid4()
    ticket = _make_ticket(team_id=other_team)

    session.get.return_value = ticket
    # agent's member teams query returns empty list
    session.execute.return_value = _MockResult(scalars_list=[])

    with pytest.raises(AppError) as exc_info:
        await ticket_service.get_scoped_ticket(session, user=agent, ticket_id=ticket.id)
    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "TICKET_NOT_FOUND"


# ---- Portal Ticket Creation ----


@pytest.mark.asyncio
async def test_create_portal_ticket_with_sla_and_sanitization(monkeypatch):
    session = _make_mock_session()
    monkeypatch.setattr(ticket_service, "_utcnow", lambda: _NOW)
    monkeypatch.setattr(
        ticket_service,
        "unique_ticket_code",
        AsyncMock(return_value="TK-20260902-1234"),
    )

    policy = SlaPolicy(
        id=uuid.uuid4(),
        priority="MEDIUM",
        first_response_minutes=60,
        resolution_minutes=240,
        pause_on_pending=True,
    )
    # Return active SLA policy
    session.execute.return_value = _MockResult(scalar=policy)

    files = [
        StoredFile(
            original_name="screenshot.png",
            stored_name="abc.png",
            storage_path="/uploads/abc.png",
            mime_type="image/png",
            size_bytes=1024,
        )
    ]

    ticket = await ticket_service.create_portal_ticket(
        session,
        requester_name="  Tran Van B <script>alert(1)</script> ",
        requester_email="  CUSTOMER@EXAMPLE.COM  ",
        subject="  Loi he thong <b>nghiem trong</b>  ",
        description="  Chi tiet mo ta loi he thong can ho tro.  ",
        category="TECHNICAL",
        files=files,
    )

    assert ticket.ticket_code == "TK-20260902-1234"
    assert "<script>" not in ticket.requester_name
    assert ticket.requester_email == "customer@example.com"
    assert ticket.priority == "MEDIUM"
    assert ticket.status == TicketStatus.OPEN.value
    assert ticket.version == 1

    # SLA deadlines calculated
    assert ticket.sla_policy_id == policy.id
    assert ticket.first_response_due_at == _NOW + timedelta(minutes=60)
    assert ticket.resolution_due_at == _NOW + timedelta(minutes=240)

    # Attachments added
    assert session.add.called
    assert session.commit.called


# ---- Update Ticket (Optimistic Locking & Fields) ----


@pytest.mark.asyncio
async def test_update_ticket_version_conflict_raises_409():
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(version=2)

    with pytest.raises(AppError) as exc_info:
        await ticket_service.update_ticket(
            session,
            ticket=ticket,
            actor=user,
            changes={"subject": "Tieu de moi"},
            reason="Update",
            expected_version=1,  # Stale version
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_update_ticket_none_on_non_nullable_field_raises_422():
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(version=1)

    with pytest.raises(AppError) as exc_info:
        await ticket_service.update_ticket(
            session,
            ticket=ticket,
            actor=user,
            changes={"subject": None},
            reason="Clear subject",
            expected_version=1,
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_ticket_success_bumps_version_and_records_history():
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(version=1)

    updated = await ticket_service.update_ticket(
        session,
        ticket=ticket,
        actor=user,
        changes={"subject": "Tieu de moi da chinh sua", "priority": "HIGH"},
        reason="Nang do uu tien theo yeu cau",
        expected_version=1,
    )

    assert updated.version == 2
    assert updated.subject == "Tieu de moi da chinh sua"
    assert updated.priority == "HIGH"
    assert session.commit.called

    # Check history rows added to session
    history_rows = [
        call[0][0]
        for call in session.add.call_args_list
        if isinstance(call[0][0], TicketHistory)
    ]
    assert len(history_rows) == 2
    fields_updated = {h.field_name for h in history_rows}
    assert fields_updated == {"subject", "priority"}


# ---- Change Status ----


@pytest.mark.asyncio
async def test_change_status_invalid_transition_raises_400():
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(status="OPEN", version=1)

    # OPEN cannot go directly to RESOLVED
    with pytest.raises(AppError) as exc_info:
        await ticket_service.change_status(
            session,
            ticket=ticket,
            actor=user,
            target="RESOLVED",
            reason="Giai quyet xong",
            expected_version=1,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_change_status_reopen_without_reason_raises_400():
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(status="RESOLVED", version=1)

    # Reopening from RESOLVED to IN_PROGRESS requires a non-empty reason (FR-TIC-11)
    with pytest.raises(AppError) as exc_info:
        await ticket_service.change_status(
            session,
            ticket=ticket,
            actor=user,
            target="IN_PROGRESS",
            reason="   ",
            expected_version=1,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "INVALID_STATUS_TRANSITION"


@pytest.mark.asyncio
async def test_change_status_to_resolved_sets_resolved_at(monkeypatch):
    session = _make_mock_session()
    monkeypatch.setattr(ticket_service, "_utcnow", lambda: _NOW)
    user = _make_user()
    ticket = _make_ticket(status="IN_PROGRESS", version=2)

    updated = await ticket_service.change_status(
        session,
        ticket=ticket,
        actor=user,
        target="RESOLVED",
        reason="Da xu ly xong van de",
        expected_version=2,
    )

    assert updated.status == "RESOLVED"
    assert updated.resolved_at == _NOW
    assert updated.version == 3
    assert session.commit.called


@pytest.mark.asyncio
async def test_change_status_reopen_clears_timestamps(monkeypatch):
    session = _make_mock_session()
    monkeypatch.setattr(ticket_service, "_utcnow", lambda: _NOW)
    user = _make_user()
    ticket = _make_ticket(status="RESOLVED", version=3)
    ticket.resolved_at = _NOW - timedelta(days=1)

    updated = await ticket_service.change_status(
        session,
        ticket=ticket,
        actor=user,
        target="IN_PROGRESS",
        reason="Khach hang phan hoi van bi loi",
        expected_version=3,
    )

    assert updated.status == "IN_PROGRESS"
    assert updated.resolved_at is None
    assert updated.closed_at is None
    assert updated.version == 4


@pytest.mark.asyncio
async def test_change_status_pending_to_in_progress_extends_deadlines(monkeypatch):
    session = _make_mock_session()
    now = _NOW
    monkeypatch.setattr(ticket_service, "_utcnow", lambda: now)
    user = _make_user()

    policy_id = uuid.uuid4()
    policy = SlaPolicy(
        id=policy_id,
        priority="HIGH",
        pause_on_pending=True,
    )
    session.get.return_value = policy

    ticket = _make_ticket(
        status="PENDING",
        version=1,
        sla_policy_id=policy_id,
        resolution_due_at=now + timedelta(hours=2),
    )
    # Simulate ticket sat in PENDING for 30 minutes
    ticket.history = [
        TicketHistory(
            event_type="STATUS_CHANGED",
            new_value="PENDING",
            created_at=now - timedelta(minutes=30),
        )
    ]

    updated = await ticket_service.change_status(
        session,
        ticket=ticket,
        actor=user,
        target="IN_PROGRESS",
        reason="Khach hang da cung cap thong tin",
        expected_version=1,
    )

    assert updated.status == "IN_PROGRESS"
    # Resolution deadline extended by 30 minutes (1800 seconds)
    expected_due = now + timedelta(hours=2, minutes=30)
    assert updated.resolution_due_at == expected_due


# ---- Assign Ticket ----


@pytest.mark.asyncio
async def test_assign_ticket_manager_cannot_assign_to_unmanaged_team():
    session = _make_mock_session()
    manager = _make_user(role=UserRole.MANAGER.value)
    ticket = _make_ticket(version=1)
    unmanaged_team = uuid.uuid4()

    # Manager's team membership query returns None
    session.execute.return_value = _MockResult(scalar=None)

    with pytest.raises(AppError) as exc_info:
        await ticket_service.assign_ticket(
            session,
            ticket=ticket,
            actor=manager,
            team_id=unmanaged_team,
            assigned_to=None,
            reason="Assign",
            expected_version=1,
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "ACCESS_DENIED"


@pytest.mark.asyncio
async def test_assign_ticket_team_not_found_raises_404():
    session = _make_mock_session()
    admin = _make_user(role=UserRole.ADMIN.value)
    ticket = _make_ticket(version=1)
    team_id = uuid.uuid4()

    session.get.return_value = None  # Team not found

    with pytest.raises(AppError) as exc_info:
        await ticket_service.assign_ticket(
            session,
            ticket=ticket,
            actor=admin,
            team_id=team_id,
            assigned_to=None,
            reason="Assign to missing team",
            expected_version=1,
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "NOT_FOUND"


@pytest.mark.asyncio
async def test_assign_ticket_invalid_assignee_raises_400():
    session = _make_mock_session()
    admin = _make_user(role=UserRole.ADMIN.value)
    ticket = _make_ticket(version=1)
    team_id = uuid.uuid4()
    team = SupportTeam(id=team_id, name="Technical Team", is_active=True)

    assignee_id = uuid.uuid4()
    # Assignee is a MANAGER, not an AGENT (is_valid_assignee requires role=AGENT)
    assignee_user = _make_user(user_id=assignee_id, role=UserRole.MANAGER.value)

    # First session.get for team, second for user
    session.get.side_effect = [team, assignee_user]
    # Membership query returns membership ID
    session.execute.return_value = _MockResult(scalar=uuid.uuid4())

    with pytest.raises(AppError) as exc_info:
        await ticket_service.assign_ticket(
            session,
            ticket=ticket,
            actor=admin,
            team_id=team_id,
            assigned_to=assignee_id,
            reason="Assign to manager instead of agent",
            expected_version=1,
        )
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "ASSIGNEE_NOT_IN_TEAM"


@pytest.mark.asyncio
async def test_assign_ticket_success_updates_fields_and_bumps_version():
    session = _make_mock_session()
    admin = _make_user(role=UserRole.ADMIN.value)
    ticket = _make_ticket(version=1)
    team_id = uuid.uuid4()
    team = SupportTeam(id=team_id, name="Technical Team", is_active=True)

    assignee_id = uuid.uuid4()
    assignee_user = _make_user(user_id=assignee_id, role=UserRole.AGENT.value, is_active=True)

    session.get.side_effect = [team, assignee_user]
    session.execute.return_value = _MockResult(scalar=uuid.uuid4())

    updated = await ticket_service.assign_ticket(
        session,
        ticket=ticket,
        actor=admin,
        team_id=team_id,
        assigned_to=assignee_id,
        reason="Giao cho agent phu trach",
        expected_version=1,
    )

    assert updated.team_id == team_id
    assert updated.assigned_to == assignee_id
    assert updated.version == 2
    assert session.commit.called
