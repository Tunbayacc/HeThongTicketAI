"""Dashboard aggregation service (S5). Role-scoped KPIs, SLA buckets, averages and
created-per-period trends over the exact Ticket List scope (FR-REP-11).

SQL does every count: status totals via GROUP BY, averages via epoch-extract, trends
via date_trunc/to_char in the reporting timezone. Python only normalizes results
(zero-fills buckets and statuses), fills the resolved window with empty buckets, and
classifies the bounded set of open SLA-tracked candidates — the SLA loop never runs
over the whole ticket set.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import TicketStatus
from app.models.ticket import SlaPolicy, Ticket, TicketHistory
from app.models.user import User
from app.services import dashboard_logic
from app.services.ticket_service import build_ticket_scope_conditions

_STATUSES = (
    TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value, TicketStatus.PENDING.value,
    TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value,
)
_OPEN_STATUSES = (
    TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value, TicketStatus.PENDING.value,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _windowed_conds(session: AsyncSession, *, user: User, from_date: date | None,
                          to_date: date | None):
    """Scope conds (exact Ticket List scope) + created_at window on the same range."""
    settings = get_settings()
    utc_from, utc_to_excl = dashboard_logic.resolve_window(
        from_date, to_date, now=_utcnow(), tz_name=settings.reporting_timezone)
    conds = await build_ticket_scope_conditions(session, user=user)
    return (
        [*conds, Ticket.created_at >= utc_from, Ticket.created_at < utc_to_excl],
        utc_from, utc_to_excl,
    )


def _range_payload(settings, utc_from: datetime, utc_to_excl: datetime) -> dict:
    """Resolved local range echoed back: dates (iso), tz, and bucket granularity."""
    tz = ZoneInfo(settings.reporting_timezone)
    to_local = (utc_to_excl - timedelta(microseconds=1)).astimezone(tz).date()
    return {
        "from": utc_from.astimezone(tz).date().isoformat(),
        "to": to_local.isoformat(),
        "timezone": settings.reporting_timezone,
        "granularity": dashboard_logic.granularity_for(utc_from, utc_to_excl),
    }


async def _avg_seconds(session: AsyncSession, conds: list, col) -> int | None:
    """Mean (col − created_at) in seconds for rows in `conds` with col set; None if none."""
    val = (await session.execute(
        select(func.avg(func.extract("epoch", col - Ticket.created_at)))
        .where(*conds, col.is_not(None))
    )).scalar_one_or_none()
    return int(round(float(val))) if val is not None else None


async def _sla_buckets(session: AsyncSession, conds: list, settings) -> dict:
    """SLA bucket counts over in-window open tracked tickets.

    Tracked = open status + a bound SlaPolicy. Pending-on-pause rows need the open
    pending window: fetched in ONE grouped query over ticket_history, mirroring
    ticket_service._pending_since semantics (latest STATUS_CHANGED -> PENDING).
    """
    now = _utcnow()
    rows = (await session.execute(
        select(Ticket.id, Ticket.status, Ticket.first_response_at,
               Ticket.first_response_due_at, Ticket.resolution_due_at,
               SlaPolicy.pause_on_pending)
        .join(SlaPolicy, SlaPolicy.id == Ticket.sla_policy_id)
        .where(*conds, Ticket.sla_policy_id.is_not(None), Ticket.status.in_(_OPEN_STATUSES))
    )).all()
    pause_ids = [
        r.id for r in rows
        if r.status == TicketStatus.PENDING.value and r.pause_on_pending
    ]
    pending_since: dict[uuid.UUID, datetime] = {}
    if pause_ids:
        history_rows = (await session.execute(
            select(TicketHistory.ticket_id, func.max(TicketHistory.created_at))
            .where(
                TicketHistory.ticket_id.in_(pause_ids),
                TicketHistory.event_type == "STATUS_CHANGED",
                # new_value is JSONB; a bare `== "PENDING"` binds VARCHAR and PG cannot
                # compare jsonb = varchar. Cast the column to text and compare against
                # the JSON text of the value ("PENDING") — matches how change_status /
                # _pending_since store and read it.
                func.cast(TicketHistory.new_value, Text) == json.dumps(TicketStatus.PENDING.value),
            )
            .group_by(TicketHistory.ticket_id)
        )).all()
        pending_since = {ticket_id: since for ticket_id, since in history_rows}
    buckets = {"tracked": 0, "on_time": 0, "due_soon": 0, "overdue": 0}
    for r in rows:
        paused = r.status == TicketStatus.PENDING.value and r.pause_on_pending
        bucket = dashboard_logic.sla_state(
            status=r.status, first_response_at=r.first_response_at,
            first_response_due_at=r.first_response_due_at,
            resolution_due_at=r.resolution_due_at,
            pause_on_pending=r.pause_on_pending,
            pending_since=pending_since.get(r.id) if paused else None,
            now=now, due_soon_minutes=settings.sla_due_soon_minutes,
        )
        if bucket is None:
            continue
        buckets["tracked"] += 1
        buckets[bucket.lower()] += 1  # ON_TIME/DUE_SOON/OVERDUE -> on_time/due_soon/overdue
    return buckets


async def summary(session: AsyncSession, *, user: User, from_date: date | None = None,
                  to_date: date | None = None) -> dict:
    """Dashboard KPIs for the caller's role-scoped view of tickets created in the range."""
    settings = get_settings()
    conds, utc_from, utc_to_excl = await _windowed_conds(
        session, user=user, from_date=from_date, to_date=to_date)
    rows = (await session.execute(
        select(Ticket.status, func.count(Ticket.id)).where(*conds).group_by(Ticket.status)
    )).all()
    by_status = {status: 0 for status in _STATUSES}
    for status, count in rows:
        if status in by_status:
            by_status[status] = int(count)
    return {
        "range": _range_payload(settings, utc_from, utc_to_excl),
        "kpi": {"total": sum(by_status.values()), "by_status": by_status},
        "sla": await _sla_buckets(session, conds, settings),
        "avg_first_response_seconds": await _avg_seconds(session, conds, Ticket.first_response_at),
        "avg_resolution_seconds": await _avg_seconds(session, conds, Ticket.resolved_at),
    }


async def trends(session: AsyncSession, *, user: User, from_date: date | None = None,
                 to_date: date | None = None) -> dict:
    """Tickets created per local day/month, split by status, over EVERY bucket in the
    range (empty buckets included, all five statuses zeroed). Counting is in PostgreSQL:
    date_trunc/AT TIME ZONE/to_char GROUP BY — rows are never downloaded to count."""
    settings = get_settings()
    tz = settings.reporting_timezone
    conds, utc_from, utc_to_excl = await _windowed_conds(
        session, user=user, from_date=from_date, to_date=to_date)
    gran = dashboard_logic.granularity_for(utc_from, utc_to_excl)
    label = func.to_char(
        func.date_trunc(gran, Ticket.created_at.op("AT TIME ZONE")(tz)),
        "YYYY-MM-DD" if gran == "day" else "YYYY-MM",  # calendar year, matches bucket_labels()
    )
    rows = (await session.execute(
        select(label.label("bucket"), Ticket.status, func.count(Ticket.id).label("n"))
        .where(*conds)
        .group_by(label, Ticket.status)
    )).all()
    labels = dashboard_logic.bucket_labels(utc_from, utc_to_excl, tz_name=tz, granularity=gran)
    index = {bucket_label: {status: 0 for status in _STATUSES} for bucket_label in labels}
    for bucket_label, status, count in rows:
        if bucket_label in index and status in index[bucket_label]:
            index[bucket_label][status] = int(count)
    return {
        "range": _range_payload(settings, utc_from, utc_to_excl),
        "buckets": [{"bucket": label, "statuses": index[label]} for label in labels],
    }
