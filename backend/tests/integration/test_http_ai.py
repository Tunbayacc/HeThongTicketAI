"""HTTP-level: AI engine routes wired in app.main over the real compose DB.

Run with the compose DB up and, in ONE command so env is set before imports:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support \
  RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_http_ai.py -q

Mirrors test_http_tickets.py: same org/token/ticket helpers, same precision of
cleanup. AI results cascade off the Ticket row, so _cleanup_org removes them.
"""

import os
import uuid

os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("AI_PROVIDER", "mock")

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
get_settings.cache_clear()

from app.core.security import hash_password  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.audit import AuditLog  # noqa: E402
from app.models.enums import TeamRole, UserRole  # noqa: E402
from app.models.team import SupportTeam, TeamMember  # noqa: E402
from app.models.ticket import Ticket  # noqa: E402
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
async def client():
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
    admin = await _add_user(f"admin.{tag}@example.com", "Admin AI HTTP", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý AI HTTP", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A AI HTTP", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B AI HTTP", UserRole.AGENT.value)
    async with AsyncSessionLocal() as s:
        team_a = SupportTeam(name=f"Team A AI HTTP {tag}", description="http ai test")
        s.add(team_a)
        await s.flush()
        team_b = SupportTeam(name=f"Team B AI HTTP {tag}", description="http ai test")
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
            await s.execute(delete(Ticket).where(Ticket.id.in_(ids)))  # cascades ai_results
        await s.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


async def _create_portal(client, email, subject="Không đăng nhập được",
                         description="Tôi quên mật khẩu, không vào được tài khoản từ sáng nay."):
    r = await client.post("/api/public/tickets", data={
        "requester_name": "Khách AI HTTP", "requester_email": email,
        "subject": subject, "description": description})
    assert r.status_code == 201, r.text
    code = r.json()["ticket_code"]
    async with AsyncSessionLocal() as s:
        t = await ticket_service.track_public(s, email=email, ticket_code=code)
        return str(t.id), code


async def _public_comment(client, ticket_id, token, content):
    r = await client.post(f"/api/tickets/{ticket_id}/comments",
                          headers={"Authorization": f"Bearer {token}"},
                          data={"content": content, "visibility": "PUBLIC"})
    assert r.status_code == 200, r.text


async def test_classify_generate_then_approve_applies_with_audit(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai1@example.com")
        d = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert d.status_code == 200 and d.json()["category"] is None and d.json()["version"] == 1

        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        assert g.status_code == 200, g.text
        out = g.json()
        assert out["status"] == "PENDING_REVIEW" and out["result_type"] == "CLASSIFICATION"
        assert out["original_output"]["category"] == "ACCOUNT"  # mock keyword hit
        assert out["low_confidence"] is False and out["confidence"] == 0.87
        assert out["model_name"] == "mock" and out["prompt_version"] == "classify-v1"
        assert len(out["input_hash"]) == 64 and out["reviewed_output"] is None

        a = await client.post(f"/api/ai/results/{out['id']}/approve", headers=headers,
                              json={"version": 1})
        assert a.status_code == 200, a.text
        assert a.json()["status"] == "APPROVED"

        d2 = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert d2.json()["category"] == "ACCOUNT" and d2.json()["priority"] == "HIGH"
        assert d2.json()["version"] == 2  # classification apply bumped it once
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_summarize_and_draft_then_reject_leave_ticket_untouched(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai2@example.com",
                                                subject="Phần mềm báo lỗi", description="Máy không khởi động được.")
        await _public_comment(client, ticket_id, token, "Khách gửi thêm thông tin.")
        s = await client.post(f"/api/tickets/{ticket_id}/ai/summarize", headers=headers)
        assert s.status_code == 200, s.text
        summary = s.json()
        assert summary["status"] == "PENDING_REVIEW" and summary["result_type"] == "SUMMARY"
        assert "problem" in summary["original_output"] and summary["confidence"] is None
        assert summary["context_cutoff_at"] is not None  # last public comment is the cutoff

        dr = await client.post(f"/api/tickets/{ticket_id}/ai/draft", headers=headers,
                               json={"instruction": "Nhã nhặn, ngắn gọn"})
        assert dr.status_code == 200, dr.text
        draft = dr.json()
        assert draft["result_type"] == "DRAFT_REPLY" and draft["original_output"]["draft"].strip()

        rj = await client.post(f"/api/ai/results/{draft['id']}/reject", headers=headers,
                               json={"reason": "Cần trao đổi nội bộ trước"})
        assert rj.status_code == 200 and rj.json()["status"] == "REJECTED"

        d = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        # The first PUBLIC staff reply above already set first_response_at and bumped
        # the ticket v1 -> v2 (SRS FR-SLA); summary/draft/reject never mutate it further.
        assert d.json()["category"] is None and d.json()["version"] == 2  # summary/draft never mutate
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_edit_classification_applies_corrected_values(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai3@example.com")
        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        out = g.json()
        corrected = dict(out["original_output"])
        corrected["category"] = "BILLING"
        corrected["priority"] = "URGENT"
        e = await client.post(f"/api/ai/results/{out['id']}/edit", headers=headers,
                              json={"reviewed_output": corrected, "version": 1,
                                    "reason": "Sai nhóm"})
        assert e.status_code == 200, e.text
        edited = e.json()
        assert edited["status"] == "EDITED" and edited["reviewed_output"]["category"] == "BILLING"

        d = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert d.json()["category"] == "BILLING" and d.json()["priority"] == "URGENT"
        assert d.json()["version"] == 2
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_approve_classification_without_version_422_and_stays_pending(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai4@example.com")
        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        out = g.json()
        a = await client.post(f"/api/ai/results/{out['id']}/approve", headers=headers, json={})
        assert a.status_code == 422, a.text
        assert a.json()["error_code"] == "VALIDATION_ERROR"
        # Nothing was consumed: the row is still reviewable with a version.
        d = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        v = d.json()["version"]
        a2 = await client.post(f"/api/ai/results/{out['id']}/approve", headers=headers,
                               json={"version": v})
        assert a2.status_code == 200 and a2.json()["status"] == "APPROVED"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_approve_stale_version_409_then_retry_ok(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai5@example.com")
        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        result_id = g.json()["id"]
        # Concurrent edit bumps the ticket version while the AI result is pending.
        p = await client.patch(f"/api/tickets/{ticket_id}", headers=headers,
                               json={"subject": "Tiêu đề đổi tay sau khi AI đề xuất", "version": 1})
        assert p.status_code == 200 and p.json()["version"] == 2

        bad = await client.post(f"/api/ai/results/{result_id}/approve", headers=headers,
                                json={"version": 1})
        assert bad.status_code == 409, bad.text
        assert bad.json()["error_code"] == "VERSION_CONFLICT"

        ok = await client.post(f"/api/ai/results/{result_id}/approve", headers=headers,
                               json={"version": 2})
        assert ok.status_code == 200 and ok.json()["status"] == "APPROVED"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_reviewing_twice_409_already_reviewed(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai6@example.com")
        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        result_id = g.json()["id"]
        first = await client.post(f"/api/ai/results/{result_id}/approve", headers=headers,
                                  json={"version": 1})
        assert first.status_code == 200
        second = await client.post(f"/api/ai/results/{result_id}/approve", headers=headers,
                                   json={"version": 2})
        assert second.status_code == 409, second.text
        assert second.json()["error_code"] == "AI_RESULT_ALREADY_REVIEWED"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_scope_anti_leak_across_teams(client):
    org = await _create_org()
    admin_tok = await _token(org["admin"])
    agent_b_tok = await _token(org["agent_b"])
    admin_h = {"Authorization": f"Bearer {admin_tok}"}
    agent_b_h = {"Authorization": f"Bearer {agent_b_tok}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai7@example.com")
        # team-B agent cannot reach the unassigned portal ticket at all.
        r = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=agent_b_h)
        assert r.status_code == 404 and r.json()["error_code"] == "TICKET_NOT_FOUND"

        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=admin_h)
        result_id = g.json()["id"]
        # Nor can he read a result whose parent ticket is out of scope.
        r2 = await client.get(f"/api/ai/results/{result_id}", headers=agent_b_h)
        assert r2.status_code == 404 and r2.json()["error_code"] == "TICKET_NOT_FOUND"
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_ai_endpoints_require_staff_auth(client):
    org = await _create_org()
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai8@example.com")
        r = await client.post(f"/api/tickets/{ticket_id}/ai/classify")
        assert r.status_code == 401
        r2 = await client.post(f"/api/ai/results/{uuid.uuid4()}/approve", json={})
        assert r2.status_code == 401
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_list_results_filter_paginate(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai9@example.com")
        await _public_comment(client, ticket_id, token, "Khách bổ sung thông tin.")
        await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        await client.post(f"/api/tickets/{ticket_id}/ai/summarize", headers=headers)

        all_rows = await client.get(f"/api/tickets/{ticket_id}/ai/results", headers=headers)
        assert all_rows.status_code == 200 and all_rows.json()["total"] == 2

        sums = await client.get(f"/api/tickets/{ticket_id}/ai/results?result_type=SUMMARY", headers=headers)
        assert sums.json()["total"] == 1 and sums.json()["items"][0]["result_type"] == "SUMMARY"

        pend = await client.get(f"/api/tickets/{ticket_id}/ai/results?status=PENDING_REVIEW", headers=headers)
        assert pend.json()["total"] == 2

        page = await client.get(f"/api/tickets/{ticket_id}/ai/results?page_size=1", headers=headers)
        assert page.json()["total"] == 2 and len(page.json()["items"]) == 1
    finally:
        await _cleanup_org(org, [ticket_id])


async def test_edit_invalid_reviewed_output_422_and_stays_pending(client):
    org = await _create_org()
    token = await _token(org["manager"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        ticket_id, _code = await _create_portal(client, "khach.ai10@example.com")
        g = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=headers)
        result_id = g.json()["id"]
        # Missing/invalid fields cannot satisfy the CLASSIFICATION OUTPUT_SCHEMA.
        bad = await client.post(f"/api/ai/results/{result_id}/edit", headers=headers,
                                json={"reviewed_output": {"category": "BACKEND"}})
        assert bad.status_code == 422, bad.text
        assert bad.json()["error_code"] == "VALIDATION_ERROR"
        d = await client.get(f"/api/ai/results/{result_id}", headers=headers)
        assert d.json()["status"] == "PENDING_REVIEW"  # nothing consumed
    finally:
        await _cleanup_org(org, [ticket_id])
