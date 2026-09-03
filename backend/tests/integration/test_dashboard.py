"""Integration: dashboard summary/trends aggregation against the real DB (S5).

Run with the compose DB up and:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support

Shared :5433 DB caveat: seeded TK-DEMO tickets and other tests' leftovers live on
the same DB. Every assertion is therefore deterministic only when the user's scope
is fully controlled (an AGENT on a freshly-created team sees exactly our fixture)
or when compared against the SAME scope/window run through reference SQL or the
Ticket List function — never against hard-coded globals. Exact-count tests use an
agent on a fresh team; role tests compare summary() to a reference count built from
the same build_ticket_scope_conditions + window; parity tests use a window back to
2000 so the (un-windowed) Ticket List result is fully inside the dashboard window.
"""

import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.enums import TeamRole, TicketStatus, UserRole
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services import dashboard_logic, dashboard_service, ticket_service

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)

_SETTINGS = get_settings()
TZ = _SETTINGS.reporting_timezone
STATUSES = tuple(s.value for s in TicketStatus)  # OPEN/IN_PROGRESS/PENDING/RESOLVED/CLOSED
_PAST = date(2000, 1, 1)  # far-past window start: covers every row the list can return


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _utcnow().astimezone(ZoneInfo(TZ)).date()


def _tag() -> str:
    return uuid.uuid4().hex[:12]


async def _add_user(email, full_name, role) -> User:
    async with AsyncSessionLocal() as s:
        u = User(full_name=full_name, email=email, password_hash=hash_password("It@123456"),
                 role=role, is_active=True)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _add_team(name) -> SupportTeam:
    async with AsyncSessionLocal() as s:
        t = SupportTeam(name=name, description="s5 test")
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


async def _add_membership(team_id, user_id, team_role: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(TeamMember(team_id=team_id, user_id=user_id, team_role=team_role, is_active=True))
        await s.commit()


async def _create_org():
    """Admin / manager (manages team_a) / agent_a (member team_a) / agent_b (team_b)."""
    tag = _tag()
    admin = await _add_user(f"admin.{tag}@example.com", "Admin S5", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý S5", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B", UserRole.AGENT.value)
    team_a = await _add_team(f"Team A {tag}")
    team_b = await _add_team(f"Team B {tag}")
    await _add_membership(team_a.id, manager.id, TeamRole.MANAGER.value)
    await _add_membership(team_a.id, agent_a.id, TeamRole.MEMBER.value)
    await _add_membership(team_b.id, agent_b.id, TeamRole.MEMBER.value)
    return {"admin": admin, "manager": manager, "agent_a": agent_a, "agent_b": agent_b,
            "team_a": team_a, "team_b": team_b, "user_ids": [admin.id, manager.id, agent_a.id, agent_b.id]}


async def _new_ticket(s: AsyncSession, *, tag, team_id=None, assigned_to=None, sla_policy_id=None,
                      status="OPEN", priority="MEDIUM", created_at=None,
                      first_response_due_at=None, resolution_due_at=None,
                      first_response_at=None, resolved_at=None) -> Ticket:
    """Add + flush one Ticket row with full control over window/SLA fields.

    Returns the flushed Ticket (id assigned) so callers can build history rows and
    track ids for cleanup without touching the session's pending-object list.
    """
    t = Ticket(ticket_code=f"TK-{tag}", requester_name="Khách S5",
               requester_email=f"khach.{tag}@example.com", subject="Vé test dashboard",
               description="Nội dung mô tả đủ dài cho vé test dashboard của S5.",
               category=None, priority=priority, status=status, team_id=team_id,
               assigned_to=assigned_to, sla_policy_id=sla_policy_id, version=1,
               first_response_due_at=first_response_due_at, resolution_due_at=resolution_due_at,
               first_response_at=first_response_at, resolved_at=resolved_at,
               created_at=created_at or _utcnow())
    s.add(t)
    await s.flush()
    return t


def _local(dt_naive_local: datetime) -> datetime:
    """Naive local wall-time -> UTC instant (reporting tz has no DST: fixed offset)."""
    return dt_naive_local.replace(tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)


def _noon(day: date) -> datetime:
    """UTC instant of local noon on `day` — safely inside that local day."""
    return _local(datetime.combine(day, time(12, 0)))


async def _cleanup_org(org, ticket_ids: list, policy_ids: list | None = None) -> None:
    """Remove everything ONE test created — and ONLY that (see module docstring)."""
    user_ids = org["user_ids"]
    team_ids = [org["team_a"].id, org["team_b"].id]
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        if ticket_ids:
            await s.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ticket_ids)))
        # Remove every ticket this org placed — by tracked id OR by our (fresh, unique)
        # teams — so an untracked fixture ticket can never block the team/user delete.
        await s.execute(delete(Ticket).where(or_(
            Ticket.id.in_(ticket_ids), Ticket.team_id.in_(team_ids))))  # cascades history/comments
        if policy_ids:
            await s.execute(delete(SlaPolicy).where(SlaPolicy.id.in_(policy_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


async def _ref_by_status(s, user, from_date, to_date) -> dict:
    """Reference aggregation: raw SQL under the SAME scope conds + window as summary."""
    conds = await ticket_service.build_ticket_scope_conditions(s, user=user)
    utc_from, utc_to_excl = dashboard_logic.resolve_window(
        from_date, to_date, now=_utcnow(), tz_name=TZ)
    rows = (await s.execute(
        select(Ticket.status, func.count(Ticket.id)).where(
            *conds, Ticket.created_at >= utc_from, Ticket.created_at < utc_to_excl)
        .group_by(Ticket.status)
    )).all()
    return {status: int(n) for status, n in rows}


async def _list_totals(s, user) -> dict:
    """Per-status totals from the Ticket List function (same user, un-windowed)."""
    out = {}
    for status in STATUSES:
        total, _items = await ticket_service.list_tickets(
            s, user=user, page=1, page_size=1, status=status)
        out[status] = total
    return out


# ---- FR-REP-01/07/08/09/11: SQL correctness + role scope vs reference -------------


async def test_summary_counts_match_reference_sql_by_role():
    org = await _create_org()
    tag = _tag()
    async with AsyncSessionLocal() as s:
        tickets = [
            await _new_ticket(s, tag=f"{tag}a1", team_id=org["team_a"].id, status="OPEN"),
            await _new_ticket(s, tag=f"{tag}a2", team_id=org["team_a"].id, status="RESOLVED",
                              resolved_at=_utcnow() + timedelta(minutes=5)),
            await _new_ticket(s, tag=f"{tag}b1", team_id=org["team_b"].id, status="OPEN"),   # team B only
            await _new_ticket(s, tag=f"{tag}u1", team_id=None, status="IN_PROGRESS"),         # unassigned pool
            await _new_ticket(s, tag=f"{tag}m1", team_id=None, assigned_to=org["manager"].id,
                              status="PENDING"),                                               # assigned to manager
        ]
        ids = [t.id for t in tickets]
        await s.commit()
    from_day = _today() - timedelta(days=1)
    try:
        async with AsyncSessionLocal() as s:
            for role in (org["admin"], org["manager"], org["agent_a"]):
                result = await dashboard_service.summary(
                    s, user=role, from_date=from_day, to_date=None)
                expected = await _ref_by_status(s, role, from_day, None)
                assert result["kpi"]["by_status"] == {st: expected.get(st, 0) for st in STATUSES}, role.email
                assert result["kpi"]["total"] == sum(expected.values())
            r = await dashboard_service.summary(s, user=org["admin"], from_date=from_day, to_date=None)
            assert r["range"]["timezone"] == TZ
            assert r["range"]["granularity"] in ("day", "month")
            assert r["range"]["from"] <= r["range"]["to"]
    finally:
        await _cleanup_org(org, ids)


# ---- FR-REP-11: direct parity with Ticket List on real rows ---------------------


async def test_summary_matches_list_ticket_totals():
    """Agent scope is fully controlled (fresh team_a): list and dashboard must agree
    on every status AND both equal the exact fixture distribution."""
    org = await _create_org()
    tag = _tag()
    dist = {"OPEN": 2, "IN_PROGRESS": 1, "PENDING": 1, "RESOLVED": 1, "CLOSED": 1}
    ids = []
    async with AsyncSessionLocal() as s:
        for status, count in dist.items():
            for k in range(count):
                t = await _new_ticket(
                    s, tag=f"{tag}{status.lower()[:2]}{k}", team_id=org["team_a"].id, status=status,
                    first_response_due_at=_utcnow() + timedelta(hours=4),
                    resolution_due_at=_utcnow() + timedelta(hours=8),
                    first_response_at=_utcnow() - timedelta(hours=1) if status != "OPEN" else None,
                    resolved_at=_utcnow() + timedelta(hours=1) if status == "RESOLVED" else None)
                ids.append(t.id)
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.summary(s, user=org["agent_a"], from_date=_PAST, to_date=None)
            list_totals = await _list_totals(s, org["agent_a"])
        assert result["kpi"]["by_status"] == dict(dist)
        assert result["kpi"]["total"] == sum(dist.values())
        # Direct parity: equals the exact list_tickets totals (real rows, real scope).
        assert {st: result["kpi"]["by_status"][st] for st in STATUSES} == list_totals
    finally:
        await _cleanup_org(org, ids)


async def test_manager_sees_no_team_pool_like_list_does():
    """A MANAGER counts the unassigned pool (intake rule) but NOT team B tickets —
    parity with the direct list result for the same user over an all-history window."""
    org = await _create_org()
    tag = _tag()
    async with AsyncSessionLocal() as s:
        tickets = [
            await _new_ticket(s, tag=f"{tag}ta", team_id=org["team_a"].id, status="OPEN"),   # manager's team
            await _new_ticket(s, tag=f"{tag}tb", team_id=org["team_b"].id, status="OPEN"),   # NOT manager's team
            await _new_ticket(s, tag=f"{tag}un", team_id=None, status="RESOLVED",            # unassigned pool
                              resolved_at=_utcnow() + timedelta(minutes=3)),
        ]
        ids = [t.id for t in tickets]
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.summary(s, user=org["manager"], from_date=_PAST, to_date=None)
            list_totals = await _list_totals(s, org["manager"])
            # The unassigned RESOLVED ticket is in the manager scope; the team-B OPEN
            # ticket is not — dashboard and list must agree exactly on every status.
            assert result["kpi"]["by_status"] == {st: list_totals[st] for st in STATUSES}
            # Control: the ADMIN (all tickets) does see the team-B ticket, so its
            # absence from the manager view is a real scope effect, not missing data.
            admin = await dashboard_service.summary(s, user=org["admin"], from_date=_PAST, to_date=None)
            assert admin["kpi"]["by_status"]["OPEN"] > result["kpi"]["by_status"]["OPEN"]
    finally:
        await _cleanup_org(org, ids)


# ---- FR-REP-04: SLA buckets ------------------------------------------------------


async def test_sla_buckets_mutually_exclusive_and_sum_to_tracked():
    org = await _create_org()
    tag = _tag()
    async with AsyncSessionLocal() as s:
        pol = SlaPolicy(name=f"mutex {tag}", priority="LOW", first_response_minutes=60,
                        resolution_minutes=1440, pause_on_pending=False,
                        effective_from=_utcnow() - timedelta(days=1), is_active=True)
        s.add(pol)
        await s.flush()
        tickets = [
            await _new_ticket(s, tag=f"{tag}on", team_id=org["team_a"].id, sla_policy_id=pol.id,
                              status="OPEN", first_response_due_at=_utcnow() + timedelta(hours=5)),
            await _new_ticket(s, tag=f"{tag}so", team_id=org["team_a"].id, sla_policy_id=pol.id,
                              status="IN_PROGRESS", first_response_at=_utcnow() - timedelta(hours=1),
                              resolution_due_at=_utcnow() + timedelta(minutes=90)),
            await _new_ticket(s, tag=f"{tag}ov", team_id=org["team_a"].id, sla_policy_id=pol.id,
                              status="OPEN", first_response_due_at=_utcnow() - timedelta(minutes=30)),
            await _new_ticket(s, tag=f"{tag}re", team_id=org["team_a"].id, sla_policy_id=pol.id,
                              status="RESOLVED", resolved_at=_utcnow() + timedelta(minutes=2),
                              first_response_due_at=_utcnow() - timedelta(hours=2)),
        ]
        ids = [t.id for t in tickets]
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.summary(s, user=org["agent_a"], from_date=None, to_date=None)
        sla = result["sla"]
        # on/soon/over each from one open ticket; the RESOLVED ticket is untracked.
        assert sla == {"tracked": 3, "on_time": 1, "due_soon": 1, "overdue": 1}
        assert sla["tracked"] == sla["on_time"] + sla["due_soon"] + sla["overdue"]
    finally:
        await _cleanup_org(org, ids, [pol.id])


async def test_sla_paused_pending_uses_effective_deadline():
    """Real pause path: a PENDING ticket on a pause_on_pending policy whose persisted
    resolution deadline is already past is ON_TIME once the open pending window is
    added back — exercises the DB pending_since query + sla_state together."""
    org = await _create_org()
    tag = _tag()
    async with AsyncSessionLocal() as s:
        pol_on = SlaPolicy(name=f"pause {tag}", priority="LOW", first_response_minutes=60,
                           resolution_minutes=120, pause_on_pending=True,
                           effective_from=_utcnow() - timedelta(days=1), is_active=True)
        pol_off = SlaPolicy(name=f"nopause {tag}", priority="LOW", first_response_minutes=60,
                            resolution_minutes=120, pause_on_pending=False,
                            effective_from=_utcnow() - timedelta(days=1), is_active=True)
        s.add_all([pol_on, pol_off])
        await s.flush()
        t_on = await _new_ticket(s, tag=f"{tag}pon", team_id=org["team_a"].id, sla_policy_id=pol_on.id,
                                 status="PENDING", resolution_due_at=_utcnow() - timedelta(minutes=30))
        t_off = await _new_ticket(s, tag=f"{tag}pof", team_id=org["team_a"].id, sla_policy_id=pol_off.id,
                                  status="PENDING", resolution_due_at=_utcnow() - timedelta(minutes=30))
        # Real TicketHistory row: the PENDING transition that determines pending_since.
        s.add(TicketHistory(ticket_id=t_on.id, changed_by=org["manager"].id,
                            event_type="STATUS_CHANGED", field_name="status",
                            old_value="IN_PROGRESS", new_value="PENDING",
                            reason=None, created_at=_utcnow() - timedelta(hours=5)))
        ids = [t_on.id, t_off.id]
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.summary(s, user=org["agent_a"], from_date=None, to_date=None)
        # pause_on_pending=true + 5h open pending -> deadline pushed ~5h past "now" ->
        # ON_TIME; the twin (pause_on_pending=false) stays OVERDUE at its past deadline.
        assert result["sla"] == {"tracked": 2, "on_time": 1, "due_soon": 0, "overdue": 1}
    finally:
        await _cleanup_org(org, ids, [pol_on.id, pol_off.id])


# ---- FR-REP-05: averages ---------------------------------------------------------


async def test_average_null_when_no_data():
    org = await _create_org()
    tag = _tag()
    async with AsyncSessionLocal() as s:
        t_open = await _new_ticket(s, tag=f"{tag}o", team_id=org["team_a"].id, status="OPEN",
                                   created_at=_noon(_today() - timedelta(days=2)))   # no response/resolution times
        t_r = await _new_ticket(s, tag=f"{tag}r", team_id=org["team_a"].id, status="RESOLVED",
                                created_at=_noon(_today()))
        t_r.first_response_at = t_r.created_at + timedelta(seconds=2.6)
        t_r.resolved_at = t_r.created_at + timedelta(seconds=7.7)
        ids = [t_open.id, t_r.id]
        await s.commit()
    early = _today() - timedelta(days=2)
    late = _today()
    try:
        async with AsyncSessionLocal() as s:
            empty = await dashboard_service.summary(
                s, user=org["agent_a"], from_date=early, to_date=early)
            assert empty["avg_first_response_seconds"] is None
            assert empty["avg_resolution_seconds"] is None
            filled = await dashboard_service.summary(
                s, user=org["agent_a"], from_date=late, to_date=late)
            assert filled["avg_first_response_seconds"] == 3      # int(round(2.6))
            assert filled["avg_resolution_seconds"] == 8          # int(round(7.7))
    finally:
        await _cleanup_org(org, ids)


# ---- FR-REP-06: window boundary + trends ----------------------------------------


async def test_window_filters_by_created_at():
    org = await _create_org()
    tag = _tag()
    day0 = _today() - timedelta(days=2)
    day2 = _today()
    from_utc = dashboard_logic.resolve_window(day0, day2, now=_utcnow(), tz_name=TZ)[0]
    async with AsyncSessionLocal() as s:
        tickets = [
            await _new_ticket(s, tag=f"{tag}in", team_id=org["team_a"].id, status="OPEN",
                              created_at=_noon(day0)),                                  # inside: day0 local noon
            await _new_ticket(s, tag=f"{tag}to", team_id=org["team_a"].id, status="OPEN",
                              created_at=_local(datetime.combine(day2, time(23, 30)))),  # inside: on the `to` day
            await _new_ticket(s, tag=f"{tag}bf", team_id=org["team_a"].id, status="OPEN",
                              created_at=from_utc - timedelta(seconds=1)),               # excluded: 1s before `from`
        ]
        ids = [t.id for t in tickets]
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.summary(
                s, user=org["agent_a"], from_date=day0, to_date=day2)
        assert result["kpi"]["by_status"]["OPEN"] == 2
        assert result["kpi"]["total"] == 2
    finally:
        await _cleanup_org(org, ids)


async def test_trends_sql_buckets_cover_whole_window():
    org = await _create_org()
    tag = _tag()
    day0 = _today() - timedelta(days=2)
    day1 = day0 + timedelta(days=1)
    day2 = _today()
    async with AsyncSessionLocal() as s:
        tickets = [
            await _new_ticket(s, tag=f"{tag}00", team_id=org["team_a"].id, status="OPEN", created_at=_noon(day0)),
            await _new_ticket(s, tag=f"{tag}01", team_id=org["team_a"].id, status="OPEN", created_at=_noon(day0)),
            await _new_ticket(s, tag=f"{tag}10", team_id=org["team_a"].id, status="OPEN", created_at=_noon(day1)),
            await _new_ticket(s, tag=f"{tag}11", team_id=org["team_a"].id, status="CLOSED", created_at=_noon(day1)),
            await _new_ticket(s, tag=f"{tag}out", team_id=org["team_a"].id, status="OPEN",
                              created_at=_noon(day0 - timedelta(days=1))),   # outside window (before `from`)
        ]
        ids = [t.id for t in tickets]
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            result = await dashboard_service.trends(
                s, user=org["agent_a"], from_date=day0, to_date=day2)
        buckets = result["buckets"]
        labels = [b["bucket"] for b in buckets]
        assert len(buckets) == 3                                   # one per day, incl. the empty day2
        assert labels == [d.strftime("%Y-%m-%d") for d in (day0, day1, day2)]
        by_label = {b["bucket"]: b["statuses"] for b in buckets}
        assert by_label[labels[0]] == {**{st: 0 for st in STATUSES}, "OPEN": 2}
        assert by_label[labels[1]] == {**{st: 0 for st in STATUSES}, "OPEN": 1, "CLOSED": 1}
        assert by_label[labels[2]] == {st: 0 for st in STATUSES}  # empty day, all five 0
        assert result["range"]["granularity"] == "day"
    finally:
        await _cleanup_org(org, ids)
