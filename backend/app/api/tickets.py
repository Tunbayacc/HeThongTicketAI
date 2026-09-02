"""Staff ticket API (SRS 8.2) — every route depends on require_roles so RBAC runs
in the dependency layer, then the Task 3 service applies per-record scoping with
the anti-leak 404 (out-of-scope == not found). Writes echo `version`; stale reads
return 409 VERSION_CONFLICT. All staff roles reach list/detail/update/status/
comments/attachments; assign + the team picker are MANAGER/ADMIN (Controller
decision 1). Staff may attach up to 5 files (SRS file rules).
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_roles
from app.core.errors import AppError
from app.db.session import get_session
from app.models.team import SupportTeam
from app.models.ticket import Attachment, Ticket
from app.models.user import User
from app.schemas.ticket import (
    AssignRequest,
    AttachmentOut,
    CommentOut,
    HistoryOut,
    StatusUpdateRequest,
    TeamMemberOut,
    TeamOut,
    TicketDetail,
    TicketListItem,
    TicketListResponse,
    TicketUpdateRequest,
)
from app.services import ticket_service
from app.services.assignment import needs_reassignment
from app.services.file_rules import parse_allowed_extensions
from app.services.storage import remove_stored, resolve_upload, store_many

router = APIRouter(tags=["tickets"])

STAFF = ("AGENT", "MANAGER", "ADMIN")
MANAGER_ADMIN = ("MANAGER", "ADMIN")

_settings = get_settings()


async def _store_and_rollback(files) -> list:
    return await store_many(
        files,
        upload_dir=Path(_settings.upload_dir),
        allowed=parse_allowed_extensions(_settings.allowed_file_types),
        max_bytes=_settings.max_upload_size_mb * 1024 * 1024,
        max_files=_settings.upload_max_files,
    )


async def _rollback(stored) -> None:
    for sf in stored:
        remove_stored(sf.storage_path)


# ---- response mappers (mirror auth.py's to_user_out) --------------------------


async def _author_names(session: AsyncSession, comments) -> dict[str, str]:
    ids = {c.author_id for c in comments if c.author_id}
    if not ids:
        return {}
    rows = (await session.execute(select(User.full_name, User.id).where(User.id.in_(ids)))).all()
    return {str(uid): name for name, uid in rows}


async def _to_detail(session: AsyncSession, ticket: Ticket) -> TicketDetail:
    comments = [c for c in ticket.comments if c.deleted_at is None]
    comments.sort(key=lambda c: c.created_at)
    authors = await _author_names(session, comments)
    attachments = sorted((a for a in ticket.attachments if a.deleted_at is None),
                         key=lambda a: a.created_at)
    history = sorted(ticket.history, key=lambda h: h.created_at, reverse=True)

    # S3 readouts: team/assignee names + FR-ASG-09 needs_reassignment (derived at
    # read time from the assignee's is_active — Controller decision 1).
    team_name = assignee_name = None
    assignee_active = None
    if ticket.team_id is not None:
        team = await session.get(SupportTeam, ticket.team_id)
        team_name = team.name if team is not None else None
    if ticket.assigned_to is not None:
        assignee = await session.get(User, ticket.assigned_to)
        if assignee is not None:
            assignee_name = assignee.full_name
            assignee_active = assignee.is_active
    flag_needs_reassignment = needs_reassignment(
        assigned_to=ticket.assigned_to is not None,
        status=ticket.status,
        assignee_active=assignee_active,
    )

    def _s(v) -> str | None:
        return str(v) if v else None

    return TicketDetail(
        id=str(ticket.id), ticket_code=ticket.ticket_code,
        requester_name=ticket.requester_name, requester_email=ticket.requester_email,
        subject=ticket.subject, description=ticket.description,
        category=ticket.category, priority=ticket.priority, status=ticket.status,
        team_id=_s(ticket.team_id), assigned_to=_s(ticket.assigned_to),
        team_name=team_name, assignee_name=assignee_name, needs_reassignment=flag_needs_reassignment,
        sla_policy_id=_s(ticket.sla_policy_id),
        first_response_due_at=ticket.first_response_due_at, resolution_due_at=ticket.resolution_due_at,
        first_response_at=ticket.first_response_at, resolved_at=ticket.resolved_at, closed_at=ticket.closed_at,
        version=ticket.version, created_at=ticket.created_at, updated_at=ticket.updated_at,
        comments=[CommentOut(id=str(c.id), author_id=_s(c.author_id),
                             author_name=authors.get(str(c.author_id)) if c.author_id else None,
                             content=c.content, visibility=c.visibility, source=c.source,
                             created_at=c.created_at, edited_at=c.edited_at) for c in comments],
        attachments=[AttachmentOut(id=str(a.id), original_name=a.original_name, mime_type=a.mime_type,
                                   size_bytes=a.size_bytes, created_at=a.created_at,
                                   uploaded_by=_s(a.uploaded_by)) for a in attachments],
        history=[HistoryOut(id=str(h.id), event_type=h.event_type, field_name=h.field_name,
                            old_value=h.old_value, new_value=h.new_value,
                            changed_by=_s(h.changed_by), reason=h.reason, created_at=h.created_at)
                 for h in history],
    )


async def _detail_after_write(session: AsyncSession, ticket: Ticket) -> TicketDetail:
    """Service returns an entity whose collection relationships are stale after new
    children (comments/attachments/history) were added; reload for the response."""
    fresh = await session.get(Ticket, ticket.id)
    # session.get returns the instance already in the identity map; expire+refresh
    # its columns eagerly so reading them below never triggers lazy IO on the
    # async connection (MissingGreenlet).
    await session.refresh(fresh)
    return await _to_detail(session, fresh)


# ---- read ---------------------------------------------------------------------


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = Query(default=None, pattern="^(OPEN|IN_PROGRESS|PENDING|RESOLVED|CLOSED)$"),
    q: str | None = Query(default=None, max_length=100),
    assigned_to_me: bool = Query(False),
    team_id: str | None = Query(default=None),
) -> TicketListResponse:
    total, items = await ticket_service.list_tickets(
        session, user=user, page=page, page_size=page_size, status=status, q=q,
        assigned_to_me=assigned_to_me, team_id=team_id,
    )
    return TicketListResponse(items=[TicketListItem(**it) for it in items],
                              total=total, page=page, page_size=page_size)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    return await _to_detail(session, ticket)


@router.get("/teams", response_model=list[TeamOut])
async def list_teams(
    user: User = Depends(require_roles(*MANAGER_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> list[TeamOut]:
    pairs = await ticket_service.teams_with_members(session, user=user)
    return [
        TeamOut(id=str(team.id), name=team.name, members=[
            TeamMemberOut(id=str(m.user.id), full_name=m.user.full_name, team_role=m.team_role,
                          role=m.user.role, is_active=m.user.is_active)
            for m in members if m.user is not None
        ])
        for team, members in pairs
    ]


# ---- writes --------------------------------------------------------------------


@router.patch("/tickets/{ticket_id}", response_model=TicketDetail)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdateRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    changes = {f: getattr(payload, f) for f in payload.model_fields_set if f not in ("reason", "version")}
    ticket = await ticket_service.update_ticket(session, ticket=ticket, actor=user,
                                                changes=changes, reason=payload.reason,
                                                expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/status", response_model=TicketDetail)
async def change_status(
    ticket_id: str,
    payload: StatusUpdateRequest,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    ticket = await ticket_service.change_status(session, ticket=ticket, actor=user,
                                                target=payload.status, reason=payload.reason,
                                                expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketDetail)
async def assign_ticket(
    ticket_id: str,
    payload: AssignRequest,
    user: User = Depends(require_roles(*MANAGER_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    ticket = await ticket_service.assign_ticket(session, ticket=ticket, actor=user,
                                                team_id=payload.team_id, assigned_to=payload.assigned_to,
                                                reason=payload.reason, expected_version=payload.version)
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/comments", response_model=TicketDetail)
async def add_comment(
    ticket_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
    content: str = Form(..., min_length=1, max_length=10000),
    visibility: str = Form(default="PUBLIC"),
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> TicketDetail:
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    stored = await _store_and_rollback(files)
    try:
        await ticket_service.add_comment(session, ticket=ticket, actor=user, content=content,
                                         visibility=visibility, files=stored or None)
    except Exception:
        await _rollback(stored)
        raise
    return await _detail_after_write(session, ticket)


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketDetail)
async def add_attachments(
    ticket_id: str,
    files: Annotated[list[UploadFile], File()],
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> TicketDetail:
    # files is required here (≥1 per SRS file rules); the comment route keeps it optional.
    ticket = await ticket_service.get_scoped_ticket(session, user=user, ticket_id=ticket_id)
    stored = await _store_and_rollback(files)
    try:
        await ticket_service.add_attachments(session, ticket=ticket, actor=user, files=stored)
    except Exception:
        await _rollback(stored)
        raise
    return await _detail_after_write(session, ticket)


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: str,
    user: User = Depends(require_roles(*STAFF)),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    try:
        aid = uuid.UUID(attachment_id)
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại.")
    row = (await session.execute(
        select(Attachment).where(Attachment.id == aid, Attachment.deleted_at.is_(None))
    )).scalar_one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại.")
    # Scope gate reuses the anti-leak 404: a staff user who cannot see the parent
    # ticket cannot learn the file exists either.
    await ticket_service.get_scoped_ticket(session, user=user, ticket_id=row.ticket_id)
    path = resolve_upload(row.storage_path)
    if not path.is_file():
        raise AppError(404, "NOT_FOUND", "Tệp không tồn tại trên máy chủ.")
    return FileResponse(path, media_type=row.mime_type, filename=row.original_name)
