import pytest

from app.services.state_machine import STATUS_FLOW, can_transition, is_reopen


def test_open_can_go_to_in_progress_and_pending_only():
    assert can_transition("OPEN", "IN_PROGRESS")
    assert can_transition("OPEN", "PENDING")
    assert not can_transition("OPEN", "RESOLVED")
    assert not can_transition("OPEN", "CLOSED")


def test_in_progress_flow():
    assert can_transition("IN_PROGRESS", "PENDING")
    assert can_transition("IN_PROGRESS", "RESOLVED")
    assert not can_transition("IN_PROGRESS", "OPEN")


def test_pending_returns_to_in_progress():
    assert can_transition("PENDING", "IN_PROGRESS")
    assert not can_transition("PENDING", "RESOLVED")


def test_resolved_and_closed_reopen_to_in_progress():
    assert can_transition("RESOLVED", "CLOSED")
    assert can_transition("RESOLVED", "IN_PROGRESS")
    assert can_transition("CLOSED", "IN_PROGRESS")
    assert not can_transition("CLOSED", "OPEN")


def test_reopen_only_from_resolved_or_closed():
    assert is_reopen("RESOLVED", "IN_PROGRESS")
    assert is_reopen("CLOSED", "IN_PROGRESS")
    assert not is_reopen("OPEN", "IN_PROGRESS")
    assert not is_reopen("IN_PROGRESS", "PENDING")


def test_unknown_statuses_are_rejected():
    assert not can_transition("OPEN", "BOGUS")
    assert not can_transition("BOGUS", "IN_PROGRESS")
    assert STATUS_FLOW["OPEN"] == {"IN_PROGRESS", "PENDING"}
