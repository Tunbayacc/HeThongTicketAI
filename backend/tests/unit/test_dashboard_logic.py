from datetime import date, datetime, timedelta, timezone

import pytest

from app.services import dashboard_logic as dl

UTC = timezone.utc
# Asia/Ho_Chi_Minh is UTC+7, no DST, so a local midnight maps deterministically.


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
