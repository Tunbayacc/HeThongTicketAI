from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.services import auth_service
from app.services.audit import coerce_ip

_NOW = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)


def test_normalize_email_trims_and_lowercases():
    assert auth_service.normalize_email("  Lan.Agent@Example.COM ") == "lan.agent@example.com"


def test_is_locked_boundary():
    assert auth_service.is_locked(_NOW + timedelta(minutes=1), now=_NOW) is True
    assert auth_service.is_locked(_NOW, now=_NOW) is False          # equal instant is not locked
    assert auth_service.is_locked(_NOW - timedelta(minutes=1), now=_NOW) is False
    assert auth_service.is_locked(None, now=_NOW) is False


def test_next_failure_state_increments_below_threshold():
    state = auth_service.next_failure_state(
        failed_login_count=2, max_attempts=5, lock_minutes=15, now=_NOW
    )
    assert state.failed_login_count == 3
    assert state.lock_triggered is False
    assert state.locked_until is None


def test_next_failure_state_locks_on_threshold_and_resets_counter():
    state = auth_service.next_failure_state(
        failed_login_count=4, max_attempts=5, lock_minutes=15, now=_NOW
    )
    assert state.lock_triggered is True
    assert state.failed_login_count == 0  # fresh window once the lock expires
    assert state.locked_until == _NOW + timedelta(minutes=15)


def test_refresh_cookie_max_age_seconds():
    settings = Settings(_env_file=None)
    assert auth_service.refresh_cookie_max_age_seconds(settings) == 7 * 86400


def test_coerce_ip_valid_kept_invalid_becomes_none():
    assert coerce_ip("203.0.113.7") == "203.0.113.7"
    assert coerce_ip("testclient") is None  # Starlette TestClient host is not an IP
    assert coerce_ip(None) is None
    assert coerce_ip("") is None
