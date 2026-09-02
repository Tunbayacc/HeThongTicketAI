"""Ticket status transition policy (SRS 3.2.2, FR-TIC-11). Pure and unit-tested."""

from app.models.enums import TicketStatus

# SRS 3.2.2: the ONLY legal transitions. A ticket never jumps to RESOLVED/CLOSED
# except from the state named; reopening always means -> IN_PROGRESS.
STATUS_FLOW: dict[str, set[str]] = {
    TicketStatus.OPEN.value: {TicketStatus.IN_PROGRESS.value, TicketStatus.PENDING.value},
    TicketStatus.IN_PROGRESS.value: {TicketStatus.PENDING.value, TicketStatus.RESOLVED.value},
    TicketStatus.PENDING.value: {TicketStatus.IN_PROGRESS.value},
    TicketStatus.RESOLVED.value: {TicketStatus.IN_PROGRESS.value, TicketStatus.CLOSED.value},
    TicketStatus.CLOSED.value: {TicketStatus.IN_PROGRESS.value},
}


def can_transition(current: str, target: str) -> bool:
    return target in STATUS_FLOW.get(current, set())


def is_reopen(current: str, target: str) -> bool:
    """Reopen = moving a RESOLVED or CLOSED ticket back to IN_PROGRESS (FR-TIC-11)."""
    return current in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value) and target == TicketStatus.IN_PROGRESS.value
