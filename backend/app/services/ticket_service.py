"""Ticket domain service: scoping + create/update/status/assign + comments/attachments.

Design spec 5.1: the service owns business rules, optimistic locking, history and
audit rows; routers parse HTTP and call here. Scope checks use Controller decision
2: ADMIN=all, MANAGER=managed teams + unassigned (team_id IS NULL) + assigned to me,
AGENT=member teams + assigned to me. An out-of-scope OR unknown ticket is the SAME
404 TICKET_NOT_FOUND (anti-leak, SRS AC-SEC). A write body must echo `version`
(optimistic lock, SRS VERSION_CONFLICT -> 409). Pause-on-pending is derived from
ticket_history (decision 3): no column, no migration.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.enums import AuditOutcome, CommentSource, TicketStatus, UserRole
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import Attachment, Comment, SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services.audit import write_audit
from app.services.sla_service import extend_deadline
from app.services.state_machine import can_transition, is_reopen
from app.services.storage import StoredFile
from app.services.ticket_code import unique_ticket_code

ENTITY_TICKET = "ticket"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _norm_email(email: str) -> str:
    return email.strip().lower()


# ---- scoping helpers ----------------------------------------------------------


async def member_team_ids(session: AsyncSession, *, user_id, manager_only: bool = False) -> list[uuid.UUID]:
    stmt = select(TeamMember.team_id).where(
        TeamMember.user_id == user_id, TeamMember.is_active.is_(True)
    )
    if manager_only:
        stmt = stmt.where(TeamMember.team_role == "MANAGER")
    return list((await session.execute(stmt)).scalars())


async def _view_team_ids(session: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """None => everything (ADMIN). MANAGER -> managed teams; AGENT -> member teams."""
    if user.role == UserRole.ADMIN.value:
        return None
    return await member_team_ids(session, user_id=user.id, manager_only=(user.role == UserRole.MANAGER.value))


def _can_view(user: User, ticket: Ticket, view_ids: list[uuid.UUID] | None) -> bool:
    if user.role == UserRole.ADMIN.value:
        return True
    if ticket.assigned_to == user.id:
        return True
    if ticket.team_id is not None and view_ids and ticket.team_id in view_ids:
        return True
    if user.role == UserRole.MANAGER.value and ticket.team_id is None:
        return True  # unassigned pool is a manager's job (Controller decision 2)
    return False


def _scope_conds(user: User, view_ids: list[uuid.UUID] | None):
    if user.role == UserRole.ADMIN.value:
        return []
    conds = [Ticket.assigned_to == user.id]
    if view_ids:
        conds.append(Ticket.team_id.in_(view_ids))
    if user.role == UserRole.MANAGER.value:
        conds.append(Ticket.team_id.is_(None))
    return [or_(*conds)]


async def get_scoped_ticket(session: AsyncSession, *, user: User, ticket_id) -> Ticket:
    """Fetch one ticket the user may view; unknown OR out-of-scope -> 404 (anti-leak)."""
    try:
        tid = uuid.UUID(str(ticket_id))
    except ValueError:
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy vé hỗ trợ.")
    ticket = await session.get(Ticket, tid)
    if ticket is None or not _can_view(user, ticket, await _view_team_ids(session, user)):
        raise AppError(404, "TICKET_NOT_FOUND", "Không tìm thấy vé hỗ trợ.")
    return ticket


# ---- history / audit / version helpers ----------------------------------------


def _add_history(session: AsyncSession, *, ticket_id, changed_by, event_type: str,
                 field_name: str | None = None, old_value=None, new_value=None, reason: str | None = None) -> None:
    session.add(TicketHistory(ticket_id=ticket_id, changed_by=changed_by, event_type=event_type,
                              field_name=field_name, old_value=old_value, new_value=new_value, reason=reason))


def _ensure_version(ticket: Ticket, expected: int) -> None:
    if ticket.version != expected:
        raise AppError(409, "VERSION_CONFLICT", "Dữ liệu đã được cập nhật ở nơi khác. Vui lòng tải lại trang và thử lại.")


def _pending_since(ticket: Ticket) -> datetime | None:
    """Latest STATUS_CHANGED -> PENDING timestamp on this (already loaded) ticket."""
    pending_times = [
        h.created_at for h in ticket.history
        if h.event_type == "STATUS_CHANGED" and h.new_value == TicketStatus.PENDING.value
    ]
    return max(pending_times) if pending_times else None


# ---- list / read --------------------------------------------------------------


_ITEM_COLS = (
    Ticket.id, Ticket.ticket_code, Ticket.subject, Ticket.category, Ticket.priority,
    Ticket.status, Ticket.requester_name, Ticket.requester_email, Ticket.team_id,
    Ticket.assigned_to, Ticket.first_response_due_at, Ticket.resolution_due_at,
    Ticket.created_at, Ticket.updated_at, Ticket.version,
)


def _row_to_item(row) -> dict:
    return {
        "id": str(row["id"]), "ticket_code": row["ticket_code"], "subject": row["subject"],
        "category": row["category"], "priority": row["priority"], "status": row["status"],
        "requester_name": row["requester_name"], "requester_email": row["requester_email"],
        "team_id": str(row["team_id"]) if row["team_id"] else None,
        "assigned_to": str(row["assigned_to"]) if row["assigned_to"] else None,
        "first_response_due_at": row["first_response_due_at"], "resolution_due_at": row["resolution_due_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"], "version": row["version"],
    }


async def list_tickets(session: AsyncSession, *, user: User, page: int, page_size: int,
                       status: str | None = None, q: str | None = None, assigned_to_me: bool = False):
    view_ids = await _view_team_ids(session, user)
    conds = _scope_conds(user, view_ids)
    if status:
        conds.append(Ticket.status == status)
    if q:
        needle = f"%{q.strip().lower()}%"
        conds.append(or_(
            func.lower(Ticket.ticket_code).like(needle),
            func.lower(Ticket.subject).like(needle),
            func.lower(Ticket.requester_name).like(needle),
            func.lower(Ticket.requester_email).like(needle),
        ))
    if assigned_to_me:
        conds.append(Ticket.assigned_to == user.id)
    total = int((await session.execute(select(func.count(Ticket.id)).where(*conds))).scalar_one())
    stmt = (
        select(*_ITEM_COLS)
        .where(*conds)
        .order_by(Ticket.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(stmt)).mappings().all()
    return total, [_row_to_item(r) for r in rows]


async def teams_with_members(session: AsyncSession, *, user: User):
    """Team + active-members pickers for the assign dialog (Controller decision 1).

    MANAGER sees only the teams they manage; ADMIN sees all teams.
    """
    if user.role == UserRole.MANAGER.value:
        ids = await member_team_ids(session, user_id=user.id, manager_only=True)
        team_stmt = select(SupportTeam).where(SupportTeam.id.in_(ids), SupportTeam.is_active.is_(True))
    else:  # ADMIN
        team_stmt = select(SupportTeam).where(SupportTeam.is_active.is_(True))
    teams = (await session.execute(team_stmt.order_by(SupportTeam.name))).scalars().all()
    result = []
    for team in teams:
        members = (
            await session.execute(
                select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.is_active.is_(True))
                .order_by(TeamMember.team_role, TeamMember.joined_at)
            )
        ).scalars().all()
        result.append((team, members))
    return result


# ---- create (public portal) ---------------------------------------------------


async def _active_sla_for_priority(session: AsyncSession, priority: str, now: datetime) -> SlaPolicy | None:
    stmt = (
        select(SlaPolicy)
        .where(
            SlaPolicy.priority == priority,
            SlaPolicy.is_active.is_(True),
            SlaPolicy.effective_from <= now,
            or_(SlaPolicy.effective_to.is_(None), SlaPolicy.effective_to > now),
        )
        .order_by(SlaPolicy.effective_from.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _add_attachment_rows(session: AsyncSession, *, ticket_id, files: list[StoredFile],
                         comment_id=None, uploaded_by=None) -> None:
    for f in files:
        session.add(Attachment(
            ticket_id=ticket_id, comment_id=comment_id, original_name=f.original_name,
            stored_name=f.stored_name, storage_path=f.storage_path, mime_type=f.mime_type,
            size_bytes=f.size_bytes, uploaded_by=uploaded_by,
        ))


async def create_portal_ticket(session: AsyncSession, *, requester_name: str, requester_email: str,
                               subject: str, description: str, category: str | None,
                               files: list[StoredFile] | None) -> Ticket:
    now = _utcnow()
    priority = "MEDIUM"  # portal tickets are MEDIUM (design spec 8 note: no priority picker on the public portal)
    ticket = Ticket(
        ticket_code=await unique_ticket_code(session),
        requester_name=requester_name.strip(),
        requester_email=_norm_email(requester_email),
        subject=subject.strip(),
        description=description.strip(),
        category=category,
        priority=priority,
        status=TicketStatus.OPEN.value,
        team_id=None, assigned_to=None, version=1,
    )
    policy = await _active_sla_for_priority(session, priority, now)
    if policy is not None:
        ticket.sla_policy_id = policy.id
        ticket.first_response_due_at = now + timedelta(minutes=policy.first_response_minutes)
        ticket.resolution_due_at = now + timedelta(minutes=policy.resolution_minutes)
    session.add(ticket)
    await session.flush()
    if files:
        _add_attachment_rows(session, ticket_id=ticket.id, files=files, comment_id=None, uploaded_by=None)
    await write_audit(session, action="TICKET_CREATED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      entity_id=ticket.id, metadata={"ticket_code": ticket.ticket_code, "priority": priority})
    await session.commit()
    await session.refresh(ticket)
    return ticket


# ---- writes (optimistic lock: expected_version must equal ticket.version) -----


async def update_ticket(session: AsyncSession, *, ticket: Ticket, actor: User, changes: dict,
                        reason: str | None, expected_version: int) -> Ticket:
    _ensure_version(ticket, expected_version)
    for field, new in changes.items():
        if new is None and field != "category":
            # Only `category` may be cleared to NULL; the rest are non-nullable.
            raise AppError(422, "VALIDATION_ERROR", "Giá trị không được để trống.")
        old = getattr(ticket, field)
        if old == new:
            continue
        setattr(ticket, field, new)
        _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="FIELD_UPDATED",
                     field_name=field, old_value=old, new_value=new, reason=reason)
    ticket.version += 1
    await write_audit(session, action="TICKET_UPDATED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      actor_id=actor.id, entity_id=ticket.id, metadata={"fields": sorted(changes)})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def change_status(session: AsyncSession, *, ticket: Ticket, actor: User, target: str,
                        reason: str | None, expected_version: int) -> Ticket:
    current = ticket.status
    _ensure_version(ticket, expected_version)
    if not can_transition(current, target):
        raise AppError(400, "INVALID_STATUS_TRANSITION",
                       f"Không thể chuyển trạng thái từ {current} sang {target}.")
    if is_reopen(current, target) and not (reason and reason.strip()):
        raise AppError(400, "INVALID_STATUS_TRANSITION",
                       "Cần nhập lý do để mở lại vé đã giải quyết/đã đóng (FR-TIC-11).")
    now = _utcnow()
    policy = await session.get(SlaPolicy, ticket.sla_policy_id) if ticket.sla_policy_id else None

    # Pause-on-pending resume: extend deadlines by the time the ticket sat in PENDING
    # (Controller decision 3, SRS FR-SLA 'deadline được bù thêm').
    if current == TicketStatus.PENDING.value and target == TicketStatus.IN_PROGRESS.value:
        pending_since = _pending_since(ticket)
        if policy is not None and policy.pause_on_pending and pending_since is not None and pending_since < now:
            pause_seconds = (now - pending_since).total_seconds()
            if pause_seconds > 0:
                extended = []
                if ticket.resolution_due_at is not None:
                    ticket.resolution_due_at = extend_deadline(ticket.resolution_due_at, pause_seconds)
                    extended.append("resolution_due_at")
                if ticket.first_response_due_at is not None and ticket.first_response_at is None:
                    ticket.first_response_due_at = extend_deadline(ticket.first_response_due_at, pause_seconds)
                    extended.append("first_response_due_at")
                if extended:
                    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="FIELD_UPDATED",
                                 field_name="sla_deadlines_extended", old_value=None,
                                 new_value={"pause_seconds": round(pause_seconds), "fields": extended},
                                 reason="Bù thời gian chờ khách hàng (SLA pause_on_pending).")

    # Closure fields (decision 5).
    if target == TicketStatus.RESOLVED.value:
        ticket.resolved_at = now
    elif target == TicketStatus.CLOSED.value:
        ticket.closed_at = now
    if is_reopen(current, target):
        ticket.resolved_at = None
        ticket.closed_at = None

    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="STATUS_CHANGED",
                 field_name="status", old_value=current, new_value=target, reason=reason)
    ticket.status = target
    ticket.version += 1
    await write_audit(session, action="TICKET_STATUS_CHANGED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"from": current, "to": target})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def assign_ticket(session: AsyncSession, *, ticket: Ticket, actor: User, team_id, assigned_to,
                        reason: str | None, expected_version: int) -> Ticket:
    _ensure_version(ticket, expected_version)
    try:
        team_uuid = uuid.UUID(str(team_id))
        assignee_uuid = uuid.UUID(str(assigned_to)) if assigned_to else None
    except ValueError:
        raise AppError(404, "NOT_FOUND", "Nhóm hỗ trợ hoặc nhân viên không tồn tại.")

    # MANAGER may only assign into a team they manage (Controller decision 1).
    if actor.role == UserRole.MANAGER.value:
        allowed = await session.execute(
            select(TeamMember.id).where(
                TeamMember.team_id == team_uuid, TeamMember.user_id == actor.id,
                TeamMember.team_role == "MANAGER", TeamMember.is_active.is_(True),
            )
        )
        if allowed.scalar_one_or_none() is None:
            raise AppError(403, "ACCESS_DENIED", "Bạn chỉ có thể gán vé vào nhóm mình quản lý.")

    team = await session.get(SupportTeam, team_uuid)
    if team is None or not team.is_active:
        raise AppError(404, "NOT_FOUND", "Nhóm hỗ trợ không tồn tại hoặc đã bị vô hiệu hóa.")

    if assignee_uuid is not None:
        membership = await session.execute(
            select(TeamMember.id).where(
                TeamMember.team_id == team_uuid, TeamMember.user_id == assignee_uuid,
                TeamMember.is_active.is_(True),
            )
        )
        if membership.scalar_one_or_none() is None:
            raise AppError(400, "ASSIGNEE_NOT_IN_TEAM",
                           "Người được gán phải là thành viên đang hoạt động của nhóm đã chọn.")

    old_snapshot = {"team_id": str(ticket.team_id) if ticket.team_id else None,
                    "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None}
    ticket.team_id = team_uuid
    ticket.assigned_to = assignee_uuid
    ticket.version += 1
    _add_history(session, ticket_id=ticket.id, changed_by=actor.id, event_type="ASSIGNED",
                 field_name=None, old_value=old_snapshot,
                 new_value={"team_id": str(team_uuid), "assigned_to": str(assignee_uuid) if assignee_uuid else None},
                 reason=reason)
    await write_audit(session, action="TICKET_ASSIGNED", entity_type=ENTITY_TICKET, outcome=AuditOutcome.SUCCESS.value,
                      actor_id=actor.id, entity_id=ticket.id,
                      metadata={"team_id": str(team_uuid), "assigned_to": str(assignee_uuid) if assignee_uuid else None})
    await session.commit()
    await session.refresh(ticket)
    return ticket


async def add_comment(session: AsyncSession, *, ticket: Ticket, actor: User, content: str,
                      visibility: str, files: list[StoredFile] | None) -> Comment:
    body = content.strip()
    if not body:
        raise AppError(422, "VALIDATION_ERROR", "Nội dung bình luận không được để trống.")
    if visibility not in ("PUBLIC", "INTERNAL"):
        raise AppError(422, "VALIDATION_ERROR", "visibility phải là PUBLIC hoặc INTERNAL.")
    now = _utcnow()
    comment = Comment(ticket_id=ticket.id, author_id=actor.id, content=body,
                      visibility=visibility, source=CommentSource.HUMAN.value)
    session.add(comment)
    await session.flush()
    if files:
        _add_attachment_rows(session, ticket_id=ticket.id, files=files, comment_id=comment.id, uploaded_by=actor.id)
    # The first PUBLIC staff reply counts as the first response (SRS FR-SLA).
    if visibility == "PUBLIC" and ticket.first_response_at is None:
        ticket.first_response_at = now
        ticket.version += 1
    await write_audit(session, action="TICKET_COMMENT_ADDED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"visibility": visibility, "public_first_response": ticket.first_response_at is not None})
    await session.commit()
    await session.refresh(comment)
    return comment


async def add_attachments(session: AsyncSession, *, ticket: Ticket, actor: User, files: list[StoredFile]) -> list[Attachment]:
    rows = []
    for f in files:
        row = Attachment(ticket_id=ticket.id, comment_id=None, original_name=f.original_name,
                         stored_name=f.stored_name, storage_path=f.storage_path, mime_type=f.mime_type,
                         size_bytes=f.size_bytes, uploaded_by=actor.id)
        session.add(row)
        rows.append(row)
    await write_audit(session, action="TICKET_ATTACHMENTS_ADDED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, actor_id=actor.id, entity_id=ticket.id,
                      metadata={"count": len(files)})
    await session.commit()
    for row in rows:
        await session.refresh(row)
    return rows


# ---- public track --------------------------------------------------------------


async def track_public(session: AsyncSession, *, email: str, ticket_code: str) -> Ticket:
    """Return a ticket only when BOTH code and (normalized) email match (FR-PUB-09).

    Wrong code, wrong email and unknown code share ONE 404 TICKET_NOT_FOUND body so
    the endpoint never confirms whether a code exists.
    """
    ticket = (
        await session.execute(
            select(Ticket).where(
                Ticket.ticket_code == ticket_code.strip().upper(),
                Ticket.requester_email == _norm_email(email),
            )
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND",
                       "Không tìm thấy vé với mã và email đã cung cấp.")
    # Expose only the public view: return a lightweight in-memory ticket whose
    # comments are PUBLIC + non-deleted only, so internal notes/AI/audit data never
    # leak to a customer response (FR-PUB-06/07). A fresh object avoids mutating the
    # persistent relationship collection (which would rewrite other rows).
    public_ticket = Ticket(
        id=ticket.id, ticket_code=ticket.ticket_code, requester_name=ticket.requester_name,
        requester_email=ticket.requester_email, subject=ticket.subject, description=ticket.description,
        category=ticket.category, priority=ticket.priority, status=ticket.status,
        first_response_due_at=ticket.first_response_due_at, resolution_due_at=ticket.resolution_due_at,
        first_response_at=ticket.first_response_at, resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at, version=ticket.version,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
    )
    public_ticket.comments = [
        Comment(id=c.id, author_id=c.author_id, content=c.content, visibility=c.visibility,
                source=c.source, ticket_id=public_ticket.id, created_at=c.created_at,
                edited_at=c.edited_at, deleted_at=c.deleted_at)
        for c in ticket.comments
        if c.visibility == "PUBLIC" and c.deleted_at is None
    ]
    await write_audit(session, action="TICKET_TRACKED", entity_type=ENTITY_TICKET,
                      outcome=AuditOutcome.SUCCESS.value, entity_id=ticket.id,
                      metadata={"ticket_code": ticket.ticket_code})
    await session.commit()
    return public_ticket
