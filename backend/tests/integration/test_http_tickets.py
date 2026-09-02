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
        # Another staff edit advances the version past v1 (reads alone never do,
        # so a stale write needs a real concurrent modification to detect).
        edit = await client.patch(f"/api/tickets/{ticket_id}", headers=headers,
                                  json={"priority": "HIGH", "version": v1})
        assert edit.status_code == 200, edit.text
        d2 = await client.get(f"/api/tickets/{ticket_id}", headers=headers)
        assert d2.json()["version"] > v1
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


async def test_teams_picker_manager_scope_and_member_resolution(client):
    org = await _create_org()
    mgr_tok = await _token(org["manager"])
    try:
        # MANAGER sees only the team they manage (team A), with members resolved.
        r = await client.get("/api/teams", headers={"Authorization": f"Bearer {mgr_tok}"})
        assert r.status_code == 200, r.text
        teams = r.json()
        assert len(teams) == 1
        assert teams[0]["id"] == str(org["team_a"].id)
        members = teams[0]["members"]
        # Reading m.user.id / m.user.full_name must not trigger lazy async IO
        # (MissingGreenlet) — each member is present with a resolvable full_name.
        by_id = {m["id"]: m["full_name"] for m in members}
        assert by_id[str(org["manager"].id)] == "Quản lý HTTP"
        assert by_id[str(org["agent_a"].id)] == "Agent A HTTP"
        assert {m["team_role"] for m in members} == {"MANAGER", "MEMBER"}
    finally:
        await _cleanup_org(org, [])
