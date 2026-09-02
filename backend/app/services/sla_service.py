"""SLA deadline math. Pure helpers (unit-tested) live here; async DB helpers used
by the ticket service are added in Task 3. Pause-on-pending is derived from
ticket_history (Controller decision 3): no column on tickets, no migration.
"""

from datetime import datetime, timedelta


def extend_deadline(due_at: datetime, pause_seconds: float) -> datetime:
    """Shift a deadline by the pause window (SRS FR-SLA: 'deadline được bù thêm')."""
    return due_at + timedelta(seconds=pause_seconds)


def deadline_state(due_at: datetime | None, now: datetime, due_soon_minutes: int) -> str:
    """Classify a deadline for the UI: overdue | due_soon | on_track | none."""
    if due_at is None:
        return "none"
    if due_at <= now:
        return "overdue"
    if due_at <= now + timedelta(minutes=due_soon_minutes):
        return "due_soon"
    return "on_track"
