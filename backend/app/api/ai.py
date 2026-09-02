"""AI engine HTTP API (SRS 8.4 / FR-AIR) — staff-only generation + human review.

Human-in-the-loop (design spec 7.4): every generate persists a PENDING_REVIEW
row and nothing is applied until a staff member approves/edits it. The AI never
self-sends, assigns, changes status, or closes a ticket. Generation endpoints
are rate-limited with Settings.ai_rate; review/list endpoints are cheap so they
stay unthrottled. Scope/anti-leak lives in get_scoped_ticket/get_result (404).
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_roles
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.models.ticket import AiResult
from app.models.user import User
from app.schemas.ai import (
    AiResultListResponse,
    AiResultOut,
    ApproveRequest,
    DraftGenerationRequest,
    EditRequest,
    RejectRequest,
)
from app.services import ai_service

router = APIRouter(tags=["ai"])

STAFF = ("AGENT", "MANAGER", "ADMIN")

_settings = get_settings()


def _to_out(row: AiResult) -> AiResultOut:
    low = False
    if row.result_type == "CLASSIFICATION" and row.confidence is not None:
        low = float(row.confidence) < _settings.ai_low_confidence_threshold
    return AiResultOut(
        id=str(row.id), ticket_id=str(row.ticket_id),
        result_type=row.result_type, status=row.status,
        model_name=row.model_name, prompt_version=row.prompt_version,
        input_hash=row.input_hash,
        confidence=float(row.confidence) if row.confidence is not None else None,
        low_confidence=low,
        original_output=row.original_output, reviewed_output=row.reviewed_output,
        review_reason=row.review_reason, error_code=row.error_code,
        context_cutoff_at=row.context_cutoff_at,
        requested_at=row.requested_at, completed_at=row.completed_at,
        reviewed_at=row.reviewed_at, latency_ms=row.latency_ms,
        requested_by=str(row.requested_by) if row.requested_by else None,
        reviewer_id=str(row.reviewer_id) if row.reviewer_id else None,
    )


# ---- generation (rate-limited; each persists a PENDING_REVIEW or FAILED row) --


@router.post("/tickets/{ticket_id}/ai/classify", response_model=AiResultOut)
@limiter.limit(_settings.ai_rate)
async def classify_ticket(
    request: Request, ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.generate_classification(session, user=user, ticket_id=ticket_id)
    return _to_out(row)


@router.post("/tickets/{ticket_id}/ai/summarize", response_model=AiResultOut)
@limiter.limit(_settings.ai_rate)
async def summarize_ticket(
    request: Request, ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.generate_summary(session, user=user, ticket_id=ticket_id)
    return _to_out(row)


@router.post("/tickets/{ticket_id}/ai/draft", response_model=AiResultOut)
@limiter.limit(_settings.ai_rate)
async def draft_reply(
    request: Request, ticket_id: str, payload: DraftGenerationRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.generate_draft(session, user=user, ticket_id=ticket_id,
                                          instruction=payload.instruction)
    return _to_out(row)


# ---- read ---------------------------------------------------------------------


@router.get("/tickets/{ticket_id}/ai/results", response_model=AiResultListResponse)
async def list_results(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    result_type: str | None = Query(default=None,
                                    pattern="^(CLASSIFICATION|SUMMARY|DRAFT_REPLY)$"),
    status: str | None = Query(default=None,
                               pattern="^(PENDING_REVIEW|APPROVED|EDITED|REJECTED|FAILED)$"),
) -> AiResultListResponse:
    total, rows = await ai_service.list_results(
        session, user=user, ticket_id=ticket_id, page=page, page_size=page_size,
        result_type=result_type, status=status)
    return AiResultListResponse(items=[_to_out(r) for r in rows], total=total,
                                page=page, page_size=page_size)


@router.get("/ai/results/{result_id}", response_model=AiResultOut)
async def get_result(
    result_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.get_result(session, user=user, result_id=result_id)
    return _to_out(row)


# ---- human review (decision endpoints; optimistic lock via version) -----------


@router.post("/ai/results/{result_id}/approve", response_model=AiResultOut)
async def approve_result(
    result_id: str, payload: ApproveRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.approve_result(session, user=user, result_id=result_id,
                                          version=payload.version, reason=payload.reason)
    return _to_out(row)


@router.post("/ai/results/{result_id}/edit", response_model=AiResultOut)
async def edit_result(
    result_id: str, payload: EditRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.edit_result(session, user=user, result_id=result_id,
                                       reviewed_output=payload.reviewed_output,
                                       version=payload.version, reason=payload.reason)
    return _to_out(row)


@router.post("/ai/results/{result_id}/reject", response_model=AiResultOut)
async def reject_result(
    result_id: str, payload: RejectRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> AiResultOut:
    row = await ai_service.reject_result(session, user=user, result_id=result_id,
                                         reason=payload.reason)
    return _to_out(row)
