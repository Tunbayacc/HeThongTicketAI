"""Unit tests for app.services.ai_service.

Verifies PII masking context serialization, prompt assembling, generation error handling,
and human-in-the-loop review actions (approve, edit, reject, optimistic locking)
without contacting Gemini or a real PostgreSQL database.
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.providers import MockProvider, ProviderError
from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import AiResultType, AiStatus, AuditOutcome, UserRole
from app.models.ticket import AiResult, Comment, Ticket
from app.models.user import User
from app.services import ai_service, ticket_service

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
    subject="Loi thanh toan don hang",
    description="Toi khong thanh toan duoc qua VNPay.",
    category="GENERAL",
    priority="MEDIUM",
    version=1,
) -> Ticket:
    t = Ticket(
        id=ticket_id or uuid.uuid4(),
        ticket_code="TK-TEST002",
        requester_name="Le Thi C",
        requester_email="customer@example.com",
        subject=subject,
        description=description,
        status="OPEN",
        priority=priority,
        category=category,
        version=version,
        team_id=None,
        assigned_to=None,
    )
    t.history = []
    t.comments = []
    t.attachments = []
    return t


def _make_user(*, role=UserRole.AGENT.value) -> User:
    return User(
        id=uuid.uuid4(),
        email="agent@example.com",
        full_name="Agent User",
        role=role,
        is_active=True,
    )


# ---- Context Serialization and PII Masking ----


def test_serialize_context_masks_pii_across_all_fields():
    subject = "Lien he voi email boss@company.com"
    desc = "So dien thoai cua toi la 0987654321, email phu: sub@company.com"
    comments = [
        ("Nhan vien goi lai vao so +84 912 345 678 nhe", _NOW),
    ]

    masked = ai_service.serialize_context(
        subject=subject,
        description=desc,
        public_comments=comments,
    )

    # Check that original emails and phones are absent
    assert "boss@company.com" not in masked
    assert "sub@company.com" not in masked
    assert "0987654321" not in masked
    assert "0912 345 678" not in masked

    # Check that placeholders are injected consistently
    assert "[EMAIL-1]" in masked
    assert "[EMAIL-2]" in masked
    assert "[PHONE-1]" in masked
    assert "[PHONE-2]" in masked


def test_assemble_classification_excludes_comments():
    ticket = _make_ticket(subject="Loi the", description="The bi khoa")
    ticket.comments = [
        Comment(id=uuid.uuid4(), content="Binh luan cong khai", visibility="PUBLIC", deleted_at=None, created_at=_NOW)
    ]
    version, system, user_prompt, input_hash, cutoff = ai_service._assemble(
        ticket, AiResultType.CLASSIFICATION.value, instruction=None
    )
    assert "Bình luận công khai:" not in user_prompt
    assert cutoff is None
    assert len(input_hash) == 64


def test_assemble_summary_includes_comments_and_cutoff():
    ticket = _make_ticket(subject="Loi the", description="The bi khoa")
    ticket.comments = [
        Comment(id=uuid.uuid4(), content="Binh luan cong khai", visibility="PUBLIC", deleted_at=None, created_at=_NOW)
    ]
    version, system, user_prompt, input_hash, cutoff = ai_service._assemble(
        ticket, AiResultType.SUMMARY.value, instruction=None
    )
    assert "Bình luận công khai:" in user_prompt
    assert "Binh luan cong khai" in user_prompt
    assert cutoff == _NOW


# ---- Low Confidence Predicate ----


def test_low_confidence_predicate(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "get_settings",
        lambda: Settings(_env_file=None, ai_low_confidence_threshold=0.75),
    )

    row_cls_low = AiResult(result_type="CLASSIFICATION", confidence=0.70)
    assert ai_service._low_confidence(row_cls_low) is True

    row_cls_high = AiResult(result_type="CLASSIFICATION", confidence=0.85)
    assert ai_service._low_confidence(row_cls_high) is False

    row_sum = AiResult(result_type="SUMMARY", confidence=0.50)
    assert ai_service._low_confidence(row_sum) is False


# ---- Generation Error Handling ----


@pytest.mark.asyncio
async def test_generate_provider_timeout_error_persists_failed_and_raises(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket()

    # Mock get_scoped_ticket
    monkeypatch.setattr(
        ticket_service,
        "get_scoped_ticket",
        AsyncMock(return_value=ticket),
    )

    # Mock provider that fails with AI_TIMEOUT
    mock_p = MockProvider(fail_mode="timeout")
    monkeypatch.setattr(ai_service, "build_provider", lambda: mock_p)

    with pytest.raises(AppError) as exc_info:
        await ai_service.generate_classification(session, user=user, ticket_id=ticket.id)

    assert exc_info.value.status_code == 504
    assert exc_info.value.error_code == "AI_TIMEOUT"

    # Verify failed AiResult row was persisted
    assert session.add.called
    failed_row = session.add.call_args[0][0]
    assert isinstance(failed_row, AiResult)
    assert failed_row.status == AiStatus.FAILED.value
    assert failed_row.error_code == "AI_TIMEOUT"
    assert session.commit.called


@pytest.mark.asyncio
async def test_generate_invalid_json_persists_failed_and_raises_502(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket()

    monkeypatch.setattr(
        ticket_service,
        "get_scoped_ticket",
        AsyncMock(return_value=ticket),
    )

    # Provider returning invalid json
    mock_p = MockProvider(fail_mode="invalid")
    monkeypatch.setattr(ai_service, "build_provider", lambda: mock_p)

    with pytest.raises(AppError) as exc_info:
        await ai_service.generate_classification(session, user=user, ticket_id=ticket.id)

    assert exc_info.value.status_code == 502
    assert exc_info.value.error_code == "AI_INVALID_RESPONSE"

    failed_row = session.add.call_args[0][0]
    assert failed_row.status == AiStatus.FAILED.value
    assert failed_row.error_code == "AI_INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_generate_classification_success(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(subject="Loi dang nhap mat khau", description="Quen mat khau khong login duoc")

    monkeypatch.setattr(
        ticket_service,
        "get_scoped_ticket",
        AsyncMock(return_value=ticket),
    )
    # Default MockProvider provides valid classification
    monkeypatch.setattr(ai_service, "build_provider", lambda: MockProvider())

    result = await ai_service.generate_classification(session, user=user, ticket_id=ticket.id)

    assert result.status == AiStatus.PENDING_REVIEW.value
    assert result.result_type == AiResultType.CLASSIFICATION.value
    assert result.original_output is not None
    assert "category" in result.original_output
    assert "priority" in result.original_output
    assert result.confidence is not None
    assert session.add.called
    assert session.commit.called


# ---- Review Actions (Approve, Edit, Reject) ----


@pytest.mark.asyncio
async def test_claim_already_reviewed_raises_409(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket()
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.APPROVED.value,  # Already approved
        result_type="CLASSIFICATION",
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    # Query with FOR UPDATE returns None because status != PENDING_REVIEW
    session.execute.return_value = _MockResult(scalar=None)

    with pytest.raises(AppError) as exc_info:
        await ai_service.approve_result(session, user=user, result_id=ai_row.id, version=1)

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "AI_RESULT_ALREADY_REVIEWED"


@pytest.mark.asyncio
async def test_approve_classification_version_conflict_raises_409(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(category="GENERAL", priority="MEDIUM", version=2)
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="CLASSIFICATION",
        original_output={"category": "BILLING", "priority": "HIGH", "confidence": 0.9, "reason": "tien nong"},
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    # Approve with stale expected_version=1 while ticket has version=2
    with pytest.raises(AppError) as exc_info:
        await ai_service.approve_result(
            session,
            user=user,
            result_id=ai_row.id,
            version=1,
            reason="Approve classification",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "VERSION_CONFLICT"


@pytest.mark.asyncio
async def test_approve_classification_applies_changes_to_ticket(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(category="GENERAL", priority="MEDIUM", version=1)
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="CLASSIFICATION",
        original_output={"category": "ACCOUNT", "priority": "HIGH", "confidence": 0.95, "reason": "Loi mat khau"},
        confidence=0.95,
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    res = await ai_service.approve_result(
        session,
        user=user,
        result_id=ai_row.id,
        version=1,
        reason="Duyet phan loai AI",
    )

    # AiResult marked approved
    assert res.status == AiStatus.APPROVED.value
    assert res.reviewer_id == user.id

    # Ticket fields updated and version incremented
    assert ticket.category == "ACCOUNT"
    assert ticket.priority == "HIGH"
    assert ticket.version == 2
    assert session.commit.called


@pytest.mark.asyncio
async def test_approve_summary_does_not_modify_ticket(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(category="GENERAL", priority="MEDIUM", version=1)
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="SUMMARY",
        original_output={
            "problem": "Loi dang nhap",
            "key_points": ["Sai pass"],
            "actions_taken": [],
            "current_status": "Cho xu ly",
            "next_steps": [],
            "warnings": [],
        },
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    res = await ai_service.approve_result(session, user=user, result_id=ai_row.id)

    assert res.status == AiStatus.APPROVED.value
    # Ticket remains untouched
    assert ticket.version == 1
    assert ticket.category == "GENERAL"


@pytest.mark.asyncio
async def test_edit_result_invalid_schema_raises_422(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket()
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="CLASSIFICATION",
        original_output={"category": "GENERAL", "priority": "MEDIUM", "confidence": 0.8, "reason": "x"},
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    # Invalid category not in allowlist
    invalid_edit = {"category": "INVALID_CAT", "priority": "HIGH", "confidence": 0.8, "reason": "chinh sua"}
    with pytest.raises(AppError) as exc_info:
        await ai_service.edit_result(
            session,
            user=user,
            result_id=ai_row.id,
            reviewed_output=invalid_edit,
            version=1,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_edit_classification_success(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(category="GENERAL", priority="MEDIUM", version=1)
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="CLASSIFICATION",
        original_output={"category": "GENERAL", "priority": "LOW", "confidence": 0.6, "reason": "x"},
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    valid_edit = {"category": "BILLING", "priority": "URGENT", "confidence": 0.95, "reason": "Loi tru tien sai"}
    res = await ai_service.edit_result(
        session,
        user=user,
        result_id=ai_row.id,
        reviewed_output=valid_edit,
        version=1,
        reason="Chinh sua thanh BILLING URGENT",
    )

    assert res.status == AiStatus.EDITED.value
    assert res.reviewed_output["category"] == "BILLING"
    assert res.reviewed_output["priority"] == "URGENT"
    assert ticket.category == "BILLING"
    assert ticket.priority == "URGENT"
    assert ticket.version == 2
    assert session.commit.called


@pytest.mark.asyncio
async def test_reject_result_marks_rejected_without_modifying_ticket(monkeypatch):
    session = _make_mock_session()
    user = _make_user()
    ticket = _make_ticket(category="GENERAL", priority="MEDIUM", version=1)
    ai_row = AiResult(
        id=uuid.uuid4(),
        ticket_id=ticket.id,
        status=AiStatus.PENDING_REVIEW.value,
        result_type="CLASSIFICATION",
        original_output={"category": "ACCOUNT", "priority": "HIGH", "confidence": 0.5, "reason": "x"},
    )

    session.get.return_value = ai_row
    monkeypatch.setattr(ticket_service, "get_scoped_ticket", AsyncMock(return_value=ticket))
    session.execute.return_value = _MockResult(scalar=ai_row)

    res = await ai_service.reject_result(
        session,
        user=user,
        result_id=ai_row.id,
        reason="AI phan loai sai hoan toan",
    )

    assert res.status == AiStatus.REJECTED.value
    assert res.review_reason == "AI phan loai sai hoan toan"
    assert ticket.version == 1
    assert ticket.category == "GENERAL"
    assert session.commit.called
