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
