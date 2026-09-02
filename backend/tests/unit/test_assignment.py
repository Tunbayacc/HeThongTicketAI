"""Unit: S3 assignment policy predicates (pure, no DB)."""

from app.services.assignment import (
    OPEN_STATUSES,
    is_open_status,
    is_valid_assignee,
    needs_reassignment,
)


def test_open_statuses_are_only_the_three_active_states():
    assert OPEN_STATUSES == frozenset({"OPEN", "IN_PROGRESS", "PENDING"})
    for s in OPEN_STATUSES:
        assert is_open_status(s) is True
    for s in ("RESOLVED", "CLOSED", "ARCHIVED", ""):
        assert is_open_status(s) is False


def test_needs_reassignment_true_only_when_open_with_inactive_assignee():
    # The FR-ASG-09 core: an open ticket whose assignee user is disabled.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=False) is True
    assert needs_reassignment(assigned_to=True, status="IN_PROGRESS", assignee_active=False) is True
    assert needs_reassignment(assigned_to=True, status="PENDING", assignee_active=False) is True


def test_needs_reassignment_false_when_active_or_unassigned_or_closed():
    # Active assignee -> no flag; no assignee -> no flag.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=True) is False
    assert needs_reassignment(assigned_to=False, status="OPEN", assignee_active=False) is False
    # Resolved/closed tickets are out of the reassignment pool regardless.
    assert needs_reassignment(assigned_to=True, status="RESOLVED", assignee_active=False) is False
    assert needs_reassignment(assigned_to=True, status="CLOSED", assignee_active=False) is False


def test_needs_reassignment_unknown_assignee_is_false():
    # assignee_active=None => the assignee row is missing/deleted => not flaggable.
    assert needs_reassignment(assigned_to=True, status="OPEN", assignee_active=None) is False


def test_is_valid_assignee_requires_active_agent_member():
    assert is_valid_assignee(role="AGENT", user_active=True, membership_active=True) is True
    assert is_valid_assignee(role="MANAGER", user_active=True, membership_active=True) is False
    assert is_valid_assignee(role="AGENT", user_active=False, membership_active=True) is False
    assert is_valid_assignee(role="AGENT", user_active=True, membership_active=False) is False
    assert is_valid_assignee(role="ADMIN", user_active=True, membership_active=True) is False
