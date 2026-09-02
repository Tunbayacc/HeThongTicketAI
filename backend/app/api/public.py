"""Public portal API — no auth (SRS FR-PUB). Create a ticket (+ optional files),
and look one up by code+email. Both are rate-limited in S2 (Controller decision 4).
Wrong code / wrong email / unknown code share ONE 404 body (FR-PUB-09 anti-leak);
errors keep the uniform {error_code, message, details} envelope (SRS 5.2/10.2).
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.schemas.public import (
    PortalCommentOut,
    PortalCreateRequest,
    PortalTicketOut,
    PortalTrackRequest,
    PortalTrackResponse,
)
from app.services import ticket_service
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import remove_stored, store_many

router = APIRouter(tags=["public"])

# Rate strings are read once at import time. Integration runs set
# RATE_LIMIT_ENABLED=false (and cache_clear) BEFORE importing app.main, so this
# module always sees a Settings built with the intended env (config.py).
_settings = get_settings()


async def _store_and_rollback(files) -> list:
    """Store attachments to disk; the caller must remove them if the DB write fails."""
    return await store_many(
        files,
        upload_dir=Path(_settings.upload_dir),
        allowed=parse_allowed_extensions(_settings.allowed_file_types),
        max_bytes=_settings.max_upload_size_mb * 1024 * 1024,
        max_files=_settings.upload_max_files,
    )


@router.post("/tickets", response_model=PortalTicketOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.public_create_rate)
async def create_ticket(
    request: Request,
    requester_name: str = Form(...),
    requester_email: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    category: str | None = Form(default=None),
    files: Annotated[list[UploadFile] | None, File()] = None,
    session: AsyncSession = Depends(get_session),
) -> PortalTicketOut:
    # Re-validate the free-form multipart fields through the schema so the SRS 10.1
    # rules (name 2-100, email format, subject 5-200, description 10-20000,
    # category in the enum) live in exactly one place.
    try:
        payload = PortalCreateRequest(
            requester_name=requester_name, requester_email=requester_email,
            subject=subject, description=description, category=category,
        )
    except ValidationError as exc:
        raise AppError(422, "VALIDATION_ERROR", "Dữ liệu không hợp lệ.",
                       details=jsonable_encoder(exc.errors()))
    stored = await _store_and_rollback(files)
    try:
        ticket = await ticket_service.create_portal_ticket(
            session, requester_name=payload.requester_name, requester_email=payload.requester_email,
            subject=payload.subject, description=payload.description, category=payload.category,
            files=stored or None,
        )
    except Exception:
        for sf in stored:
            remove_stored(sf.storage_path)
        raise
    return PortalTicketOut(ticket_code=ticket.ticket_code, status=ticket.status,
                           subject=ticket.subject, created_at=ticket.created_at)


@router.post("/track", response_model=PortalTrackResponse)
@limiter.limit(_settings.public_track_rate)
async def track_ticket(
    payload: PortalTrackRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PortalTrackResponse:
    ticket = await ticket_service.track_public(session, email=payload.email, ticket_code=payload.ticket_code)
    public_comments = sorted(
        (c for c in ticket.comments if c.visibility == "PUBLIC" and c.deleted_at is None),
        key=lambda c: c.created_at,
    )
    return PortalTrackResponse(
        ticket_code=ticket.ticket_code, subject=ticket.subject, status=ticket.status,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
        comments=[PortalCommentOut(id=str(c.id), content=c.content, created_at=c.created_at)
                  for c in public_comments],
    )
