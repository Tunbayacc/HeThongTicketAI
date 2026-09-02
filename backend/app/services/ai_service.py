"""AI service: Human-in-the-loop generation + review of ai_results rows.

Design spec 7.4: AI proposes, staff disposes. Generation masks PII, truncates to a
bounded context and persists a PENDING_REVIEW row; approve/edit/reject transition
it. Only an APPROVED/EDITED CLASSIFICATION mutates the ticket (category/priority)
under the optimistic-lock version — SUMMARY/DRAFT_REPLY never touch ticket data.
Services commit; the router only maps HTTP and ORM rows to response schemas.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import (
    build_classify_prompt,
    build_draft_prompt,
    build_summarize_prompt,
    truncate_context,
)
from app.ai.providers import ProviderError, build_provider
from app.ai.schemas import OUTPUT_SCHEMAS
from app.ai.pii_masker import mask_text
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.enums import AiResultType, AiStatus, AuditOutcome, Visibility
from app.models.ticket import AiResult, Ticket, TicketHistory
from app.models.user import User
from app.services import ticket_service
from app.services.audit import write_audit

_HTTP_BY_CODE = {"AI_RATE_LIMITED": 429, "AI_TIMEOUT": 504,
                 "AI_INVALID_RESPONSE": 502, "AI_UNAVAILABLE": 502}
_ENTITY_AI = "ai_result"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_context(*, subject: str, description: str,
                      public_comments: list) -> str:
    """Masked, labeled text that becomes the model's DỮ LIỆU payload.

    public_comments: list of (content, created_at). Masking runs once over the whole
    assembled block so placeholder numbering is stable across fields.
    """
    parts = [f"Tiêu đề: {subject}", f"Mô tả: {description}"]
    if public_comments:
        parts.append("Bình luận công khai:")
        for content, created_at in public_comments:
            stamp = created_at.astimezone(timezone.utc).isoformat() if created_at else ""
            parts.append(f"- [{stamp}] {content}")
    return mask_text("\n".join(parts))


def _public_comments(ticket: Ticket) -> list:
    """(content, created_at) for PUBLIC, non-deleted comments, oldest first."""
    rows = [c for c in ticket.comments
            if c.deleted_at is None and c.visibility == Visibility.PUBLIC.value]
    rows.sort(key=lambda c: c.created_at)
    return [(c.content, c.created_at) for c in rows]


def _assemble(ticket: Ticket, result_type: str, instruction: str | None):
    """Return (prompt_version, system_prompt, user_prompt, input_hash, cutoff_at)."""
    include_comments = result_type in ("SUMMARY", "DRAFT_REPLY")
    public = _public_comments(ticket) if include_comments else []
    masked = serialize_context(subject=ticket.subject, description=ticket.description,
                               public_comments=public)
    sent, _trunc = truncate_context(masked)  # hash exactly what is embedded in the prompt
    input_hash = hashlib.sha256(sent.encode("utf-8")).hexdigest()
    cutoff = public[-1][1] if public else None
    if cutoff is not None:
        cutoff_note = "Dữ liệu bình luận lấy tới " + cutoff.astimezone(timezone.utc).isoformat()
    else:
        cutoff_note = None
    if result_type == AiResultType.CLASSIFICATION.value:
        version, system, user = build_classify_prompt(masked)
    elif result_type == AiResultType.SUMMARY.value:
        version, system, user = build_summarize_prompt(masked, cutoff_note=cutoff_note)
    else:
        version, system, user = build_draft_prompt(masked, instruction=instruction,
                                                   cutoff_note=cutoff_note)
    return version, system, user, input_hash, cutoff


async def _persist_failed(session, *, user, ticket, result_type, provider,
                          prompt_version, input_hash, cutoff, error_code, latency_ms) -> None:
    now = _utcnow()
    session.add(AiResult(ticket_id=ticket.id, requested_by=user.id, result_type=result_type,
                         status=AiStatus.FAILED.value, model_name=provider.model_name,
                         prompt_version=prompt_version, input_hash=input_hash,
                         context_cutoff_at=cutoff, error_code=error_code,
                         requested_at=now, completed_at=now, latency_ms=latency_ms))
    await session.commit()


async def _generate(session, *, user: User, ticket_id, result_type: str,
                    instruction: str | None = None) -> AiResult:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    version, system, user_prompt, input_hash, cutoff = _assemble(ticket, result_type, instruction)
    try:
        provider = build_provider()
    except ProviderError as exc:
        # Provider cannot even be constructed (misconfig): nothing to persist.
        raise AppError(_HTTP_BY_CODE.get(exc.code, 502), exc.code, exc.message)
    started = _utcnow()
    try:
        raw = await provider.generate(result_type=result_type, system_prompt=system,
                                      user_prompt=user_prompt)
    except ProviderError as exc:
        latency_ms = int((_utcnow() - started).total_seconds() * 1000)
        await _persist_failed(session, user=user, ticket=ticket, result_type=result_type,
                              provider=provider, prompt_version=version, input_hash=input_hash,
                              cutoff=cutoff, error_code=exc.code, latency_ms=latency_ms)
        raise AppError(_HTTP_BY_CODE.get(exc.code, 502), exc.code, exc.message)
    latency_ms = int((_utcnow() - started).total_seconds() * 1000)
    try:
        data = json.loads(raw)
        validated = OUTPUT_SCHEMAS[result_type].model_validate(data)
    except (ValueError, TypeError, KeyError):
        await _persist_failed(session, user=user, ticket=ticket, result_type=result_type,
                              provider=provider, prompt_version=version, input_hash=input_hash,
                              cutoff=cutoff, error_code="AI_INVALID_RESPONSE", latency_ms=latency_ms)
        raise AppError(502, "AI_INVALID_RESPONSE", "Phản hồi AI không hợp lệ.")
    now = _utcnow()
    row = AiResult(
        ticket_id=ticket.id, requested_by=user.id, result_type=result_type,
        status=AiStatus.PENDING_REVIEW.value, model_name=provider.model_name,
        prompt_version=version, input_hash=input_hash, context_cutoff_at=cutoff,
        original_output=validated.model_dump(), reviewed_output=None,
        confidence=validated.confidence if result_type == AiResultType.CLASSIFICATION.value else None,
        requested_at=now, completed_at=now, latency_ms=latency_ms,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def generate_classification(session, *, user: User, ticket_id) -> AiResult:
    return await _generate(session, user=user, ticket_id=ticket_id,
                           result_type=AiResultType.CLASSIFICATION.value)


async def generate_summary(session, *, user: User, ticket_id) -> AiResult:
    return await _generate(session, user=user, ticket_id=ticket_id,
                           result_type=AiResultType.SUMMARY.value)


async def generate_draft(session, *, user: User, ticket_id,
                         instruction: str | None = None) -> AiResult:
    return await _generate(session, user=user, ticket_id=ticket_id,
                           result_type=AiResultType.DRAFT_REPLY.value, instruction=instruction)


# ---- read ---------------------------------------------------------------------


async def list_results(session, *, user: User, ticket_id, page: int = 1, page_size: int = 10,
                       result_type: str | None = None, status: str | None = None):
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    conds = [AiResult.ticket_id == ticket.id]
    if result_type:
        conds.append(AiResult.result_type == result_type)
    if status:
        conds.append(AiResult.status == status)
    total = int((await session.execute(
        select(func.count(AiResult.id)).where(*conds))).scalar_one())
    rows = (await session.execute(
        select(AiResult).where(*conds)
        .order_by(AiResult.requested_at.desc(), AiResult.id.desc())
        .offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return total, list(rows)


async def get_result(session, *, user: User, result_id) -> AiResult:
    try:
        rid = uuid.UUID(str(result_id))
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Kết quả AI không tồn tại.")
    row = await session.get(AiResult, rid)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Kết quả AI không tồn tại.")
    # Anti-leak: an invisible parent ticket makes the result invisible too.
    await ticket_service.get_scoped_ticket(session, user=user, ticket_id=row.ticket_id)
    return row


# ---- review -------------------------------------------------------------------


async def _claim(session, *, user: User, result_id):
    """Load the row, gate parent-ticket scope, then lock-claim the PENDING_REVIEW
    transition. A concurrent reviewer gets 409 (only one disposition wins)."""
    try:
        rid = uuid.UUID(str(result_id))
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Kết quả AI không tồn tại.")
    row = await session.get(AiResult, rid)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Kết quả AI không tồn tại.")
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=row.ticket_id)
    claimed = (await session.execute(
        select(AiResult).where(AiResult.id == rid,
                               AiResult.status == AiStatus.PENDING_REVIEW.value)
        .with_for_update())).scalar_one_or_none()
    if claimed is None:
        raise AppError(409, "AI_RESULT_ALREADY_REVIEWED",
                       "Kết quả AI này đã được duyệt/xử lý trước đó.")
    return claimed, ticket


def _effective_output(row: AiResult, effective: dict | None) -> dict:
    if effective is not None:
        return effective
    return row.original_output if row.original_output is not None else {}


def _low_confidence(row: AiResult) -> bool:
    if row.result_type != AiResultType.CLASSIFICATION.value or row.confidence is None:
        return False
    return float(row.confidence) < get_settings().ai_low_confidence_threshold


async def _apply_classification(session, *, user, ticket: Ticket, row: AiResult,
                                effective: dict, reason: str | None,
                                expected_version: int | None) -> bool:
    """Mirror ticket_service.update_ticket inline (it commits internally). Only
    actual changes bump the version (Controller decision B)."""
    changes: dict[str, str] = {}
    for field in ("category", "priority"):
        val = effective.get(field)
        if val is not None and getattr(ticket, field) != val:
            changes[field] = val
    if not changes:
        return False
    if expected_version is None:
        raise AppError(422, "VALIDATION_ERROR",
                       "Thiếu version của vé để áp dụng phân loại AI.")
    ticket_service._ensure_version(ticket, expected_version)
    for field, new in changes.items():
        old = getattr(ticket, field)
        setattr(ticket, field, new)
        session.add(TicketHistory(ticket_id=ticket.id, changed_by=user.id,
                                  event_type="FIELD_UPDATED", field_name=field,
                                  old_value=old, new_value=new, reason=reason))
    ticket.version += 1
    await write_audit(session, action="TICKET_UPDATED", entity_type="ticket",
                      outcome=AuditOutcome.SUCCESS.value, actor_id=user.id,
                      entity_id=ticket.id, metadata={"fields": sorted(changes)})
    return True


async def _audit_review(session, *, user, row: AiResult, ticket_id, decision: str,
                        applied: bool) -> None:
    await write_audit(session, action="AI_RESULT_REVIEWED", entity_type=_ENTITY_AI,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=user.id, entity_id=row.id,
                      metadata={"result_type": row.result_type, "decision": decision,
                                "ticket_id": str(ticket_id), "applied": applied,
                                "low_confidence": _low_confidence(row)})


async def _mark_reviewed(session, *, row: AiResult, user: User, status: str,
                         effective: dict | None, reason: str | None) -> None:
    now = _utcnow()
    row.status = status
    if effective is not None:
        row.reviewed_output = effective
    row.reviewer_id = user.id
    row.review_reason = reason
    row.reviewed_at = now


async def approve_result(session, *, user: User, result_id,
                         version: int | None = None, reason: str | None = None) -> AiResult:
    row, ticket = await _claim(session, user=user, result_id=result_id)
    applied = False
    if row.result_type == AiResultType.CLASSIFICATION.value:
        effective = _effective_output(row, None)
        applied = await _apply_classification(session, user=user, ticket=ticket, row=row,
                                              effective=effective, reason=reason,
                                              expected_version=version)
    await _mark_reviewed(session, row=row, user=user, status=AiStatus.APPROVED.value,
                         effective=None, reason=reason)
    await _audit_review(session, user=user, row=row, ticket_id=ticket.id,
                        decision=AiStatus.APPROVED.value, applied=applied)
    await session.commit()
    await session.refresh(row)
    return row


async def edit_result(session, *, user: User, result_id, reviewed_output: dict,
                      version: int | None = None, reason: str | None = None) -> AiResult:
    row, ticket = await _claim(session, user=user, result_id=result_id)
    # The human's correction must itself satisfy the output schema (BR-11).
    try:
        validated = OUTPUT_SCHEMAS[row.result_type].model_validate(reviewed_output)
    except (ValueError, TypeError, KeyError):
        raise AppError(422, "VALIDATION_ERROR", "Nội dung chỉnh sửa không hợp lệ.")
    effective = validated.model_dump()
    applied = False
    if row.result_type == AiResultType.CLASSIFICATION.value:
        applied = await _apply_classification(session, user=user, ticket=ticket, row=row,
                                              effective=effective, reason=reason,
                                              expected_version=version)
    await _mark_reviewed(session, row=row, user=user, status=AiStatus.EDITED.value,
                         effective=effective, reason=reason)
    await _audit_review(session, user=user, row=row, ticket_id=ticket.id,
                        decision=AiStatus.EDITED.value, applied=applied)
    await session.commit()
    await session.refresh(row)
    return row


async def reject_result(session, *, user: User, result_id,
                        reason: str | None = None) -> AiResult:
    row, ticket = await _claim(session, user=user, result_id=result_id)
    await _mark_reviewed(session, row=row, user=user, status=AiStatus.REJECTED.value,
                         effective=None, reason=reason)
    await _audit_review(session, user=user, row=row, ticket_id=ticket.id,
                        decision=AiStatus.REJECTED.value, applied=False)
    await session.commit()
    await session.refresh(row)
    return row
