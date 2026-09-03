"""HTTP-level: dashboard routes wired in app.main over the real compose DB (S5).

Run with the compose DB up and, in ONE command so env is set before imports:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support \
  RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_http_dashboard.py -q

Mirrors test_http_ai.py: same ASGITransport client + _token/_create_org/_cleanup_org
helpers. The dashboard ADMIN scope is the whole system, so the exact-count test
places its fixture on a past local day PROVEN empty before insert (single GROUP BY
over recent days); that makes admin/manager/agent totals fixture-exact regardless of
demo seed or other suites' leftovers on the shared :5433 DB.
"""

import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("AI_PROVIDER", "mock")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
get_settings.cache_clear()

from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.enums import TeamRole, TicketStatus, UserRole  # noqa: E402
from app.models.team import SupportTeam, TeamMember  # noqa: E402
from app.models.ticket import Ticket  # noqa: E402
from app.models.user import RefreshToken, User  # noqa: E402
from app.services import auth_service, dashboard_service  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)

_PASSWORD = "It@123456"
_SETTINGS = get_settings()
TZ = _SETTINGS.reporting_timezone
STATUS_KEYS = tuple(s.value for s in TicketStatus)  # OPEN/IN_PROGRESS/PENDING/RESOLVED/CLOSED


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


@pytest.fixture(scope="module")
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    """Admin / manager (manages team_a) / agent_a (member team_a) / agent_b (team_b)."""
    tag = _tag()
    admin = await _add_user(f"admin.{tag}@example.com", "Admin HTTP S5", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý HTTP S5", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A HTTP S5", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B HTTP S5", UserRole.AGENT.value)
    async with AsyncSessionLocal() as s:
        team_a = SupportTeam(name=f"Team A HTTP S5 {tag}", description="http s5 test")
        s.add(team_a)
        await s.flush()
        team_b = SupportTeam(name=f"Team B HTTP S5 {tag}", description="http s5 test")
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


async def _cleanup_org(org, ticket_ids) -> None:
    ids = list(ticket_ids)
    user_ids = org["user_ids"]
    team_ids = [org["team_a"].id, org["team_b"].id]
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        if ids:
            await s.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
            await s.execute(delete(Ticket).where(Ticket.id.in_(ids)))  # cascades history/comments
        await s.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


def _local_utc(day: date, hour: int = 12) -> datetime:
    """UTC instant of local time `hour:00` on `day` (reporting tz has no DST)."""
    return datetime.combine(day, time(hour, 0), tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)


async def _pick_empty_day(max_back: int = 60) -> date:
    """A past local date (never today) that currently holds ZERO tickets anywhere.

    Choosing such a day makes the whole-window fixture the ONLY rows the admin scope
    can count in it — the one deterministic way to assert exact admin/manager/agent
    totals over the shared :5433 DB (admin sees every ticket in the system).
    """
    today = _utcnow().astimezone(ZoneInfo(TZ)).date()
    oldest = today - timedelta(days=max_back)
    label = func.to_char(
        func.date_trunc("day", Ticket.created_at.op("AT TIME ZONE")(TZ)), "YYYY-MM-DD")
    async with AsyncSessionLocal() as s:
        occupied = set((await s.execute(
            select(label).where(Ticket.created_at >= _local_utc(oldest, 0))
        )).scalars())
    for offset in range(1, max_back + 1):
        day = today - timedelta(days=offset)
        if day.isoformat() not in occupied:
            return day
    raise RuntimeError("no ticket-free local day found in the last %d days" % max_back)


async def _insert_ticket(org, *, tag, status, team_id=None, assigned_to=None,
                         created_at=None) -> Ticket:
    async with AsyncSessionLocal() as s:
        t = Ticket(ticket_code=f"TK-{tag}", requester_name="Khách HTTP S5",
                   requester_email=f"khach.{tag}@example.com", subject="Vé test dashboard HTTP",
                   description="Nội dung mô tả đủ dài cho vé test dashboard HTTP của S5.",
                   category=None, priority="MEDIUM", status=status, team_id=team_id,
                   assigned_to=assigned_to, sla_policy_id=None, version=1,
                   created_at=created_at or _utcnow())
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


# ---- auth gate ---------------------------------------------------------------


async def test_dashboard_requires_auth(client):
    for path in ("/api/dashboard/summary", "/api/dashboard/trends"):
        r = await client.get(path)
        assert r.status_code == 401, r.text
        assert r.json()["error_code"] == "AUTH_TOKEN_EXPIRED"


async def test_dashboard_every_staff_role_reaches_both_endpoints(client):
    org = await _create_org()
    try:
        for user in (org["admin"], org["manager"], org["agent_a"], org["agent_b"]):
            headers = {"Authorization": f"Bearer {await _token(user)}"}
            for path in ("/api/dashboard/summary", "/api/dashboard/trends"):
                r = await client.get(path, headers=headers)
                assert r.status_code == 200, r.text
    finally:
        await _cleanup_org(org, [])


async def test_summary_and_trends_shape_admin(client):
    org = await _create_org()
    headers = {"Authorization": f"Bearer {await _token(org['admin'])}"}
    try:
        s = await client.get("/api/dashboard/summary", headers=headers)
        assert s.status_code == 200, s.text
        body = s.json()
        rng = body["range"]
        assert set(rng) == {"from", "to", "timezone", "granularity"}
        assert rng["timezone"] == TZ and rng["granularity"] in ("day", "month")
        assert len(rng["from"]) == 10 and len(rng["to"]) == 10  # YYYY-MM-DD
        by = body["kpi"]["by_status"]
        assert set(by) == set(STATUS_KEYS)
        assert all(isinstance(v, int) and v >= 0 for v in by.values())
        assert sum(by.values()) == body["kpi"]["total"]
        assert set(body["sla"]) == {"tracked", "on_time", "due_soon", "overdue"}
        assert body["sla"]["tracked"] == body["sla"]["on_time"] + body["sla"]["due_soon"] + body["sla"]["overdue"]
        for key in ("avg_first_response_seconds", "avg_resolution_seconds"):
            assert key in body and (body[key] is None or isinstance(body[key], int))

        t = await client.get("/api/dashboard/trends", headers=headers)
        assert t.status_code == 200, t.text
        tbody = t.json()
        assert set(tbody) == {"range", "buckets"}
        # Default 30-day window resolves to exactly 30 local day buckets, every one
        # present with all five statuses 0-filled (FR-REP-06 coverage guarantee).
        assert tbody["range"]["granularity"] == "day"
        assert len(tbody["buckets"]) == 30
        assert tbody["buckets"][0]["bucket"] == tbody["range"]["from"]
        for b in tbody["buckets"]:
            assert set(b["statuses"]) == set(STATUS_KEYS)
            assert sum(b["statuses"].values()) >= 0
    finally:
        await _cleanup_org(org, [])


async def test_http_validation_envelope_for_both_bad_ranges(client):
    org = await _create_org()
    headers = {"Authorization": f"Bearer {await _token(org['manager'])}"}
    try:
        # (a) inverted range: business rule raised inside the router -> AppError envelope
        bad = await client.get(
            "/api/dashboard/summary?from=2026-09-09&to=2026-09-01", headers=headers)
        assert bad.status_code == 422, bad.text
        assert bad.json() == {"error_code": "VALIDATION_ERROR",
                              "message": "Khoảng thời gian không hợp lệ.", "details": None}

        # (b) malformed date: FastAPI's own query-param validation -> the SHARED
        # RequestValidationError handler in app/core/errors.py, not a dashboard format.
        for path in ("/api/dashboard/summary", "/api/dashboard/trends"):
            mal = await client.get(f"{path}?from=not-a-date", headers=headers)
            assert mal.status_code == 422, mal.text
            body = mal.json()
            assert set(body) == {"error_code", "message", "details"}
            assert body["error_code"] == "VALIDATION_ERROR"
            assert body["message"] == "Dữ liệu không hợp lệ."
            assert isinstance(body["details"], list) and body["details"]
            loc = body["details"][0].get("loc", [])
            assert "query" in loc and "from" in loc
    finally:
        await _cleanup_org(org, [])


async def test_http_summary_exact_counts_per_role(client):
    """Fixed dataset on an empty past day -> exact per-role totals (FR-REP-07/08/09).

    Scopes on arbitrary data are NOT subset-related, so only fixture-exact counts
    are meaningful — never an admin >= manager >= agent inequality. Fixture (all on
    `day`): t_a1 OPEN in team_a, t_a2 RESOLVED in team_a, t_b IN_PROGRESS in team_b,
    t_un CLOSED unassigned.
      admin scope (whole system):     4
      manager scope (team_a + pool):  t_a1 + t_a2 + t_un = 3
      agent_a scope (own team):       t_a1 + t_a2 = 2
    """
    org = await _create_org()
    day = await _pick_empty_day()
    tag = _tag()
    try:
        ta1 = await _insert_ticket(org, tag=f"{tag}a1", status="OPEN",
                                   team_id=org["team_a"].id, assigned_to=org["agent_a"].id,
                                   created_at=_local_utc(day))
        ta2 = await _insert_ticket(org, tag=f"{tag}a2", status="RESOLVED",
                                   team_id=org["team_a"].id, created_at=_local_utc(day))
        tb = await _insert_ticket(org, tag=f"{tag}b", status="IN_PROGRESS",
                                  team_id=org["team_b"].id, created_at=_local_utc(day))
        tun = await _insert_ticket(org, tag=f"{tag}un", status="CLOSED",
                                   created_at=_local_utc(day))
        ticket_ids = [ta1.id, ta2.id, tb.id, tun.id]
        qs = f"from={day.isoformat()}&to={day.isoformat()}"

        expect = {
            "admin": {"total": 4, "by_status": {"OPEN": 1, "IN_PROGRESS": 1, "PENDING": 0,
                                                "RESOLVED": 1, "CLOSED": 1}},
            "manager": {"total": 3, "by_status": {"OPEN": 1, "IN_PROGRESS": 0, "PENDING": 0,
                                                  "RESOLVED": 1, "CLOSED": 1}},
            "agent_a": {"total": 2, "by_status": {"OPEN": 1, "IN_PROGRESS": 0, "PENDING": 0,
                                                  "RESOLVED": 1, "CLOSED": 0}},
        }
        for key, user in (("admin", org["admin"]), ("manager", org["manager"]),
                          ("agent_a", org["agent_a"])):
            tok = await _token(user)
            r = await client.get(f"/api/dashboard/summary?{qs}",
                                 headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 200, r.text
            kpi = r.json()["kpi"]
            assert kpi == expect[key], (key, kpi)
            # HTTP pipeline is a transparent pass-through of the service payload.
            async with AsyncSessionLocal() as s:
                svc = await dashboard_service.summary(s, user=user,
                                                      from_date=day, to_date=day)
            assert svc["kpi"] == kpi and svc["range"]["from"] == day.isoformat()
    finally:
        await _cleanup_org(org, ticket_ids)
