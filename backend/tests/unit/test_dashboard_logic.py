from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services import dashboard_logic as dl

UTC = timezone.utc
TZ = "Asia/Ho_Chi_Minh"
# Asia/Ho_Chi_Minh is UTC+7, no DST, so a local midnight maps deterministically.

# Deterministic reference "now" for sla_state/bucket_labels (pure functions).
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
DM = 120  # sla_due_soon_minutes from Settings


def test_resolve_window_converts_hcm_midnights_to_utc():
    f, t = dl.resolve_window(date(2026, 8, 5), date(2026, 8, 5),
                             now=datetime(2026, 8, 10, tzinfo=UTC),
                             tz_name="Asia/Ho_Chi_Minh")
    # 2026-08-05 00:00 +07 == 2026-08-04 17:00 UTC; exclusive end = next day midnight.
    assert f == datetime(2026, 8, 4, 17, 0, tzinfo=UTC)
    assert t == datetime(2026, 8, 5, 17, 0, tzinfo=UTC)


def test_resolve_window_defaults_to_rolling_30_days():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)  # local date 2026-08-10
    f, t = dl.resolve_window(None, None, now=now, tz_name="Asia/Ho_Chi_Minh")
    assert f == datetime(2026, 7, 11, 17, 0, tzinfo=UTC)   # local (today-29) midnight
    assert t == datetime(2026, 8, 10, 17, 0, tzinfo=UTC)   # local tomorrow midnight


def test_resolve_window_rejects_from_after_to():
    with pytest.raises(ValueError):
        dl.resolve_window(date(2026, 8, 6), date(2026, 8, 5),
                          now=datetime(2026, 8, 10, tzinfo=UTC),
                          tz_name="Asia/Ho_Chi_Minh")


def test_resolve_window_clamps_future_to_today():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    f, t = dl.resolve_window(date(2026, 8, 9), date(2026, 12, 31),
                             now=now, tz_name="Asia/Ho_Chi_Minh")
    assert t == datetime(2026, 8, 10, 17, 0, tzinfo=UTC)  # clamped to local today+1


def _hcm_utc(day: date) -> datetime:
    """UTC instant of Asia/Ho_Chi_Minh local midnight of `day` (no DST: +07 fixed)."""
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(TZ)).astimezone(UTC)


# ---- sla_state ----------------------------------------------------------------
# Common defaults; each test overrides only the axis it exercises.


def _sla(**overrides):
    args = dict(status="OPEN", first_response_at=None, first_response_due_at=None,
                resolution_due_at=None, pause_on_pending=False, pending_since=None,
                now=NOW, due_soon_minutes=DM)
    args.update(overrides)
    return dl.sla_state(**args)


def test_sla_responded_open_uses_resolution_deadline():
    # A first response exists, so the (already past) first-response deadline is
    # irrelevant: the resolution deadline 5h out classifies ON_TIME.
    assert _sla(status="OPEN", first_response_at=NOW - timedelta(hours=1),
                first_response_due_at=NOW - timedelta(minutes=10),
                resolution_due_at=NOW + timedelta(hours=5)) == "ON_TIME"


def test_sla_unresponded_open_with_only_past_first_due_is_overdue():
    assert _sla(status="OPEN", first_response_due_at=NOW - timedelta(minutes=5),
                resolution_due_at=None) == "OVERDUE"


def test_sla_untracked_when_resolved_closed_or_no_deadline():
    # RESOLVED/CLOSED are never tracked even with deadlines set.
    assert _sla(status="RESOLVED", resolution_due_at=NOW + timedelta(hours=1)) is None
    assert _sla(status="CLOSED", first_response_due_at=NOW + timedelta(hours=1)) is None
    # No deadline at all on an open status -> untracked.
    assert _sla(status="OPEN") is None
    assert _sla(status="PENDING", first_response_due_at=None, resolution_due_at=None) is None


def test_sla_due_soon_boundary_is_inclusive_at_due_soon_minutes():
    assert _sla(first_response_at=NOW - timedelta(minutes=1),
                resolution_due_at=NOW + timedelta(minutes=DM)) == "DUE_SOON"  # exactly at boundary
    assert _sla(first_response_at=NOW - timedelta(minutes=1),
                resolution_due_at=NOW + timedelta(minutes=DM + 1)) == "ON_TIME"  # past boundary


def test_sla_paused_pending_uses_effective_deadline():
    # Pending for 5h with pause_on_pending pushes the persisted (past) deadline
    # 5h into the future -> ON_TIME. Same ticket without the pause rule stays OVERDUE.
    pending_since = NOW - timedelta(hours=5)
    resolution_due_at = NOW - timedelta(hours=1)
    assert _sla(status="PENDING", pause_on_pending=True, pending_since=pending_since,
                resolution_due_at=resolution_due_at) == "ON_TIME"
    assert _sla(status="PENDING", pause_on_pending=False, pending_since=pending_since,
                resolution_due_at=resolution_due_at) == "OVERDUE"
    # A recent pending window that only partially covers the shortfall -> DUE_SOON,
    # proving the extension is by the open pending window, not a full reset.
    assert _sla(status="PENDING", pause_on_pending=True,
                pending_since=NOW - timedelta(minutes=90),
                resolution_due_at=NOW - timedelta(hours=1)) == "DUE_SOON"


def test_sla_returns_exactly_one_bucket_for_tracked_input():
    # Single return value: a tracked ticket is classified into exactly one of the
    # three buckets and never into any other string (or two buckets).
    cases = [
        dict(status="OPEN", first_response_at=NOW - timedelta(minutes=1),
             resolution_due_at=NOW + timedelta(hours=5)),
        dict(status="IN_PROGRESS", first_response_at=NOW - timedelta(hours=2),
             resolution_due_at=NOW + timedelta(minutes=90)),
        dict(status="PENDING", pause_on_pending=True, pending_since=NOW - timedelta(hours=3),
             resolution_due_at=NOW - timedelta(minutes=30)),
        dict(status="OPEN", first_response_due_at=NOW - timedelta(seconds=1)),
    ]
    for case in cases:
        bucket = _sla(**case)
        assert bucket in ("ON_TIME", "DUE_SOON", "OVERDUE")


# ---- bucket_labels ------------------------------------------------------------


def test_bucket_labels_day_three_local_days_ending_on_to():
    labels = dl.bucket_labels(_hcm_utc(date(2026, 8, 5)), _hcm_utc(date(2026, 8, 8)),
                              tz_name=TZ, granularity="day")
    assert labels == ["2026-08-05", "2026-08-06", "2026-08-07"]


def test_bucket_labels_month_partial_first_and_last_month():
    labels = dl.bucket_labels(_hcm_utc(date(2026, 7, 29)), _hcm_utc(date(2026, 9, 1)),
                              tz_name=TZ, granularity="month")
    assert labels == ["2026-07", "2026-08"]


def test_bucket_labels_month_crosses_new_year_calendar():
    # 2026-12-29 .. 2027-01-02 (month granularity) must use calendar years —
    # "2026-12" then "2027-01", NOT ISO week-year labels.
    labels = dl.bucket_labels(_hcm_utc(date(2026, 12, 29)), _hcm_utc(date(2027, 1, 3)),
                              tz_name=TZ, granularity="month")
    assert labels == ["2026-12", "2027-01"]


def test_bucket_labels_single_day_window_never_empty():
    labels = dl.bucket_labels(_hcm_utc(date(2026, 8, 5)), _hcm_utc(date(2026, 8, 6)),
                              tz_name=TZ, granularity="day")
    assert labels == ["2026-08-05"]
