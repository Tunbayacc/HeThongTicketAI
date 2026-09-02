from datetime import datetime, timedelta, timezone

from app.services.sla_service import deadline_state, extend_deadline

_NOW = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)


def test_extend_deadline_shifts_by_pause():
    due = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert extend_deadline(due, 3600) == due + timedelta(hours=1)


def test_deadline_state_overdue_due_soon_on_track_none():
    assert deadline_state(_NOW - timedelta(minutes=1), _NOW, 120) == "overdue"
    assert deadline_state(_NOW + timedelta(minutes=30), _NOW, 120) == "due_soon"
    assert deadline_state(_NOW + timedelta(hours=5), _NOW, 120) == "on_track"
    assert deadline_state(None, _NOW, 120) == "none"
