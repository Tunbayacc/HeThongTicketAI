"""Integration: AI service flows against the real DB (design spec 10 S4).

Run with the compose DB up and, in ONE command:
  INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support \
  RATE_LIMIT_ENABLED=false .venv/Scripts/python -m pytest tests/integration/test_ai_service.py -q

Every test builds a throwaway org (+ ticket) and removes exactly what it created.
Ticket deletion cascades comments/history/attachments AND ai_results (FK CASCADE).
"""

import json
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.core.errors import AppError
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.enums import AiStatus, TeamRole, TicketStatus, UserRole
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import AiResult, Ticket
from app.models.user import User
from app.services import ai_service, ticket_service

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


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
        t = SupportTeam(name=name, description="s4 ai test")
        s.add(t)
        await s.commit()
        await s.refresh(t)
        return t


async def _add_membership(team_id, user_id, team_role: str) -> None:
    async with AsyncSessionLocal() as s:
        s.add(TeamMember(team_id=team_id, user_id=user_id, team_role=team_role, is_active=True))
        await s.commit()


async def _create_org():
    tag = _tag()
    admin = await _add_user(f"admin.{tag}@example.com", "Admin AI", UserRole.ADMIN.value)
    manager = await _add_user(f"mgr.{tag}@example.com", "Quản lý AI", UserRole.MANAGER.value)
    agent_a = await _add_user(f"aga.{tag}@example.com", "Agent A AI", UserRole.AGENT.value)
    agent_b = await _add_user(f"agb.{tag}@example.com", "Agent B AI", UserRole.AGENT.value)
    team_a = await _add_team(f"Team A AI {tag}")
    team_b = await _add_team(f"Team B AI {tag}")
    await _add_membership(team_a.id, manager.id, TeamRole.MANAGER.value)
    await _add_membership(team_a.id, agent_a.id, TeamRole.MEMBER.value)
    await _add_membership(team_b.id, agent_b.id, TeamRole.MEMBER.value)
    return {"admin": admin, "manager": manager, "agent_a": agent_a, "agent_b": agent_b,
            "team_a": team_a, "team_b": team_b, "user_ids": [admin.id, manager.id, agent_a.id, agent_b.id]}


async def _create_ticket(subject="Không đăng nhập được", description="Tôi quên mật khẩu, không vào được tài khoản từ sáng nay."):
    tag = _tag()
    async with AsyncSessionLocal() as s:
        t = await ticket_service.create_portal_ticket(
            s, requester_name="Khách AI", requester_email=f"khach.ai.{tag}@example.com",
            subject=subject, description=description, category=None, files=None)
        return t


async def _add_public_comment(ticket_id, actor, content) -> datetime:
    async with AsyncSessionLocal() as s:
        t = await ticket_service.get_scoped_ticket(s, user=actor, ticket_id=ticket_id)
        await ticket_service.add_comment(s, ticket=t, actor=actor, content=content,
                                         visibility="PUBLIC", files=None)
        return t.comments[-1].created_at if t.comments else None


async def _cleanup_org(org, ticket_ids: list) -> None:
    user_ids = org["user_ids"]
    team_ids = [org["team_a"].id, org["team_b"].id]
    ids = list(ticket_ids)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        if ids:
            await s.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
            await s.execute(delete(Ticket).where(Ticket.id.in_(ids)))  # cascades ai_results too
        await s.execute(delete(TeamMember).where(TeamMember.user_id.in_(user_ids)))
        await s.execute(delete(TeamMember).where(TeamMember.team_id.in_(team_ids)))
        await s.execute(delete(User).where(User.id.in_(user_ids)))
        await s.execute(delete(SupportTeam).where(SupportTeam.id.in_(team_ids)))
        await s.commit()


class _EchoProvider:
    """Returns the full user prompt as a valid DRAFT so a test can inspect exactly
    what the model would have received (context-hygiene assertions)."""
    model_name = "recorder"

    async def generate(self, *, result_type, system_prompt, user_prompt):
        return json.dumps({"draft": user_prompt, "tone": "x",
                           "assumptions": [], "warnings": []}, ensure_ascii=False)

    async def probe(self):
        return True


async def test_generate_classification_persists_pending_review():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            assert row.status == AiStatus.PENDING_REVIEW.value
            assert row.result_type == "CLASSIFICATION"
            assert row.model_name == "mock"
            assert row.prompt_version == "classify-v1"
            assert row.original_output["category"] == "ACCOUNT"  # mock keyword hit
            assert row.confidence is not None and float(row.confidence) > 0
            assert row.context_cutoff_at is None
            assert len(row.input_hash) == 64
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_generate_summary_and_cutoff_from_last_public_comment():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"],
                                             content="Bình luận công khai một.", visibility="PUBLIC", files=None)
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"],
                                             content="Bình luận công khai hai.", visibility="PUBLIC", files=None)
            # t.comments was an eager snapshot taken before the adds (FK-set children
            # do not propagate into an already-loaded collection), so reload it.
            await s.refresh(t, attribute_names=["comments"])
            last = t.comments[-1].created_at
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_summary(s, user=org["admin"], ticket_id=ticket.id)
            assert row.status == AiStatus.PENDING_REVIEW.value
            assert row.result_type == "SUMMARY"
            assert row.prompt_version == "summarize-v1"
            assert row.context_cutoff_at is not None
            assert abs((row.context_cutoff_at - last).total_seconds()) < 2
            assert row.confidence is None
            assert "problem" in row.original_output
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_generate_draft_with_instruction_persists():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_draft(s, user=org["manager"], ticket_id=ticket.id,
                                                  instruction="Nhã nhặn, ngắn gọn.")
            assert row.status == AiStatus.PENDING_REVIEW.value
            assert row.result_type == "DRAFT_REPLY"
            assert row.prompt_version == "draft-v1"
            assert row.original_output["draft"].strip()
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_context_hygiene_masks_pii_and_excludes_internal(monkeypatch):
    org = await _create_org()
    ticket = await _create_ticket(subject="Vé có email", description="Mô tả thường.")
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"],
                                             content="Khách đã gửi abc@x.com và 0912 345 678.", visibility="PUBLIC", files=None)
            await ticket_service.add_comment(s, ticket=t, actor=org["agent_a"],
                                             content="NỘI BỘ: bí mật nội bộ tuyệt đối.", visibility="INTERNAL", files=None)
        monkeypatch.setattr(ai_service, "build_provider", lambda: _EchoProvider())
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_draft(s, user=org["admin"], ticket_id=ticket.id)
            echoed = row.original_output["draft"]
            assert "abc@x.com" not in echoed
            assert "0912 345 678" not in echoed
            assert "[EMAIL-1]" in echoed and "[PHONE-1]" in echoed
            assert "NỘI BỘ: bí mật nội bộ" not in echoed  # internal never sent
            assert "Bình luận công khai:" in echoed
            assert "Tiêu đề: Vé có email" in echoed
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_approve_classification_applies_changes_with_history_and_audit():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.category is None and t.priority == "MEDIUM"
            approved = await ai_service.approve_result(s, user=org["admin"], result_id=row.id,
                                                       version=t.version, reason="OK với đề xuất")
            assert approved.status == AiStatus.APPROVED.value
            assert approved.reviewed_output is None
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.category == "ACCOUNT" and t.priority == "HIGH"
            assert t.version == 2
            await s.refresh(t, attribute_names=["history"])
            field_rows = [h for h in t.history if h.event_type == "FIELD_UPDATED"]
            assert {h.field_name for h in field_rows} == {"category", "priority"}
        async with AsyncSessionLocal() as s:
            audits = (await s.execute(
                select(AuditLog).where(AuditLog.action == "AI_RESULT_REVIEWED"))).scalars().all()
            assert any(a.metadata_.get("decision") == "APPROVED" and a.metadata_.get("applied") for a in audits)
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_approve_noop_classification_keeps_version():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            t.category = "ACCOUNT"
            t.priority = "HIGH"
            await s.commit()
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            approved = await ai_service.approve_result(s, user=org["admin"], result_id=row.id,
                                                       version=t.version)
            assert approved.status == AiStatus.APPROVED.value
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.version == 1  # no field changed -> no version consumed
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_edit_classification_applies_reviewed_output():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            corrected = dict(row.original_output)
            corrected["category"] = "BILLING"
            corrected["priority"] = "URGENT"
            edited = await ai_service.edit_result(s, user=org["admin"], result_id=row.id,
                                                  reviewed_output=corrected, version=t.version,
                                                  reason="Sai nhóm")
            assert edited.status == AiStatus.EDITED.value
            assert edited.reviewed_output["category"] == "BILLING"
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.category == "BILLING" and t.priority == "URGENT"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_reject_leaves_ticket_and_version_unchanged():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            rejected = await ai_service.reject_result(s, user=org["admin"], result_id=row.id,
                                                      reason="Không phù hợp")
            assert rejected.status == AiStatus.REJECTED.value
            assert rejected.review_reason == "Không phù hợp"
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.category is None and t.version == 1  # rejected classification changes nothing
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_approve_summary_and_draft_do_not_touch_ticket():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        for gen in (ai_service.generate_summary, ai_service.generate_draft):
            async with AsyncSessionLocal() as s:
                row = await gen(s, user=org["admin"], ticket_id=ticket.id)
                t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
                approved = await ai_service.approve_result(s, user=org["admin"], result_id=row.id)
                assert approved.status == AiStatus.APPROVED.value
        async with AsyncSessionLocal() as s:
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            assert t.version == 1 and t.category is None  # never mutated by summary/draft
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_reviewing_twice_raises_already_reviewed():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            await ai_service.approve_result(s, user=org["admin"], result_id=row.id, version=t.version)
            with pytest.raises(AppError) as exc:
                await ai_service.reject_result(s, user=org["admin"], result_id=row.id)
            assert exc.value.status_code == 409 and exc.value.error_code == "AI_RESULT_ALREADY_REVIEWED"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_approve_stale_version_conflict_and_result_stays_pending():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            # A concurrent edit bumps the ticket version between generate and approve.
            t = await ticket_service.get_scoped_ticket(s, user=org["admin"], ticket_id=ticket.id)
            await ticket_service.update_ticket(s, ticket=t, actor=org["admin"],
                                               changes={"subject": "Tiêu đề bị sửa sau khi AI đề xuất"},
                                               reason="chỉnh tay", expected_version=t.version)
        async with AsyncSessionLocal() as s:
            with pytest.raises(AppError) as exc:
                await ai_service.approve_result(s, user=org["admin"], result_id=row.id, version=1)
            assert exc.value.status_code == 409 and exc.value.error_code == "VERSION_CONFLICT"
        async with AsyncSessionLocal() as s:
            row = await ai_service.get_result(s, user=org["admin"], result_id=row.id)
            assert row.status == AiStatus.PENDING_REVIEW.value  # nothing consumed
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_scope_anti_leak_generate_and_get_result():
    org = await _create_org()
    ticket = await _create_ticket()  # unassigned portal ticket
    try:
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            result_id = row.id
        # agent_b (team B) cannot reach the ticket -> generation 404.
        async with AsyncSessionLocal() as s:
            with pytest.raises(AppError) as exc:
                await ai_service.generate_classification(s, user=org["agent_b"], ticket_id=ticket.id)
            assert exc.value.status_code == 404 and exc.value.error_code == "TICKET_NOT_FOUND"
        # agent_b cannot read a result of a ticket they cannot see (same 404 shape).
        async with AsyncSessionLocal() as s:
            with pytest.raises(AppError) as exc2:
                await ai_service.get_result(s, user=org["agent_b"], result_id=result_id)
            assert exc2.value.status_code == 404 and exc2.value.error_code == "TICKET_NOT_FOUND"
        # Unknown result id is 404 NOT_FOUND.
        async with AsyncSessionLocal() as s:
            with pytest.raises(AppError) as exc3:
                await ai_service.get_result(s, user=org["admin"], result_id=uuid.uuid4())
            assert exc3.value.status_code == 404 and exc3.value.error_code == "NOT_FOUND"
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_failed_modes_persist_failed_rows(monkeypatch):
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        for idx, (fail, code, status) in enumerate(
                (("timeout", "AI_TIMEOUT", 504), ("invalid", "AI_INVALID_RESPONSE", 502)), start=1):
            monkeypatch.setenv("AI_MOCK_FAIL", fail)
            async with AsyncSessionLocal() as s:
                with pytest.raises(AppError) as exc:
                    await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
                assert exc.value.status_code == status and exc.value.error_code == code
                total, rows = await ai_service.list_results(s, user=org["admin"], ticket_id=ticket.id)
                assert total == idx and rows[0].status == AiStatus.FAILED.value
                assert rows[0].error_code == code and rows[0].latency_ms is not None
        monkeypatch.delenv("AI_MOCK_FAIL")
        # Success returns to normal and appends a PENDING_REVIEW row.
        async with AsyncSessionLocal() as s:
            row = await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            assert row.status == AiStatus.PENDING_REVIEW.value
    finally:
        await _cleanup_org(org, [ticket.id])


async def test_list_results_filters_and_paginates():
    org = await _create_org()
    ticket = await _create_ticket()
    try:
        async with AsyncSessionLocal() as s:
            await ai_service.generate_classification(s, user=org["admin"], ticket_id=ticket.id)
            await ai_service.generate_summary(s, user=org["admin"], ticket_id=ticket.id)
            total, rows = await ai_service.list_results(s, user=org["admin"], ticket_id=ticket.id)
            assert total == 2
            total, rows = await ai_service.list_results(s, user=org["admin"], ticket_id=ticket.id,
                                                        result_type="SUMMARY")
            assert total == 1 and rows[0].result_type == "SUMMARY"
            total, rows = await ai_service.list_results(s, user=org["admin"], ticket_id=ticket.id,
                                                        page=1, page_size=1)
            assert total == 2 and len(rows) == 1
    finally:
        await _cleanup_org(org, [ticket.id])
