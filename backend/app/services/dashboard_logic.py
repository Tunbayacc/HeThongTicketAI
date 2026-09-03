"""Pure dashboard math: reporting-window resolution and granularity.

No DB imports. Everything takes explicit `now` so unit tests are deterministic.
Day boundaries are resolved in the reporting IANA timezone (default Asia/Ho_Chi_Minh)
then converted to UTC for SQL filters: created_at >= from_utc AND created_at < to_excl_utc.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


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
