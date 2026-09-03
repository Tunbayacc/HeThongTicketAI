from datetime import datetime, timezone
import pytest

from app.services.sla_policy_service import intervals_overlap

UTC = timezone.utc


def test_intervals_overlap_detected():
    # A: [2026-01-01, 2026-06-01), B: [2026-05-01, 2026-12-01) -> Overlap
    a_from = datetime(2026, 1, 1, tzinfo=UTC)
    a_to = datetime(2026, 6, 1, tzinfo=UTC)
    b_from = datetime(2026, 5, 1, tzinfo=UTC)
    b_to = datetime(2026, 12, 1, tzinfo=UTC)
    assert intervals_overlap(a_from, a_to, b_from, b_to) is True


def test_intervals_touching_boundary_no_overlap():
    # A: [2026-01-01, 2026-06-01), B: [2026-06-01, None) -> No overlap
    a_from = datetime(2026, 1, 1, tzinfo=UTC)
    a_to = datetime(2026, 6, 1, tzinfo=UTC)
    b_from = datetime(2026, 6, 1, tzinfo=UTC)
    b_to = None
    assert intervals_overlap(a_from, a_to, b_from, b_to) is False


def test_intervals_open_ended_overlap():
    # A: [2026-01-01, None), B: [2026-05-01, None) -> Overlap
    a_from = datetime(2026, 1, 1, tzinfo=UTC)
    b_from = datetime(2026, 5, 1, tzinfo=UTC)
    assert intervals_overlap(a_from, None, b_from, None) is True
