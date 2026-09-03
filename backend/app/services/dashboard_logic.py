"""Pure dashboard math: reporting-window resolution, granularity, SLA buckets, labels.

No DB imports. Everything takes explicit `now` so unit tests are deterministic.
Day boundaries are resolved in the reporting IANA timezone (default Asia/Ho_Chi_Minh)
then converted to UTC for SQL filters: created_at >= from_utc AND created_at < to_excl_utc.
sla_state reuses the pure sla_service deadline math (also a no-DB module).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.sla_service import deadline_state, extend_deadline


def _local_midnight_utc(day: date, tz_name: str) -> datetime:
    local = datetime.combine(day, time.min, tzinfo=ZoneInfo(tz_name))
    return local.astimezone(timezone.utc)


def resolve_window(
    from_date: date | None,
    to_date: date | None,
    *,
    now: datetime,
    tz_name: str,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    """Return (utc_from, utc_to_excl). from_date <= to_date (ValueError otherwise)."""
    tz = ZoneInfo(tz_name)
    today = now.astimezone(tz).date()
    to = to_date or today
    if to > today:
        to = today
    if from_date is None:
        from_date = to - timedelta(days=default_days - 1)
    if from_date > to:
        raise ValueError("from_date must not be after to_date")
    return _local_midnight_utc(from_date, tz_name), _local_midnight_utc(to + timedelta(days=1), tz_name)


def granularity_for(utc_from: datetime, utc_to_excl: datetime) -> str:
    return "day" if (utc_to_excl - utc_from).days <= 62 else "month"


def sla_state(*, status, first_response_at, first_response_due_at, resolution_due_at,
              pause_on_pending, pending_since, now, due_soon_minutes):
    """SLA bucket for ONE current ticket, or None if it is not SLA-tracked.

    Tracked iff status in {OPEN, IN_PROGRESS, PENDING} and the still-relevant
    deadline is set. Primary deadline = first-response due (only while no first
    response yet) else resolution due. While PENDING on a pause_on_pending policy,
    add the open pending window to the effective deadline (mirrors the extension
    ticket_service.change_status applies on exit). ON_TIME/DUE_SOON/OVERDUE are
    mutually exclusive; tracked rows always produce exactly one bucket.
    """
    if status not in ("OPEN", "IN_PROGRESS", "PENDING"):
        return None
    primary = None
    if first_response_at is None and first_response_due_at is not None:
        primary = first_response_due_at
    elif resolution_due_at is not None:
        primary = resolution_due_at
    if primary is None:
        return None
    if (status == "PENDING" and pause_on_pending and pending_since is not None
            and pending_since < now):
        primary = extend_deadline(primary, (now - pending_since).total_seconds())
    state = deadline_state(primary, now, due_soon_minutes)  # overdue|due_soon|on_track|none
    return {"overdue": "OVERDUE", "due_soon": "DUE_SOON", "on_track": "ON_TIME"}.get(state)


def bucket_labels(utc_from: datetime, utc_to_excl: datetime, *, tz_name: str, granularity: str) -> list[str]:
    """Local-date label list for every reporting bucket in [utc_from, utc_to_excl).

    Iterates local dates (day granularity) or first-of-month steps (month
    granularity) from utc_from's local date through the local date of the last
    instant of the window (utc_to_excl − 1 µs). Calendar years (not ISO-week
    years). Callers pass from < to so the span always holds ≥ 1 bucket.
    """
    tz = ZoneInfo(tz_name)
    last = (utc_to_excl - timedelta(microseconds=1)).astimezone(tz).date()
    first = utc_from.astimezone(tz).date()
    if granularity == "month":
        first = first.replace(day=1)
        last = last.replace(day=1)
    labels: list[str] = []
    cursor = first
    while cursor <= last:
        labels.append(cursor.strftime("%Y-%m-%d" if granularity == "day" else "%Y-%m"))
        if granularity == "day":
            cursor += timedelta(days=1)
        else:
            cursor = cursor.replace(year=cursor.year + 1, month=1) if cursor.month == 12 \
                else cursor.replace(month=cursor.month + 1)
    return labels
