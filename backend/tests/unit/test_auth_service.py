"""Unit tests for app.services.auth_service.

Verifies login, token refresh, and logout business logic with mocked DB session.
No real PostgreSQL database is used.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import security
from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import AuditOutcome, UserRole
from app.models.user import RefreshToken, User
from app.services import auth_service

_NOW = datetime(2026, 9, 2, 8, 0, 0, tzinfo=timezone.utc)
_PASSWORD = "CorrectPassword123!"
_HASHED_PW = security.hash_password(_PASSWORD)


class _MockResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        mock = MagicMock()
        mock.all.return_value = self._scalars_list
        mock.__iter__.return_value = iter(self._scalars_list)
        return mock


def _make_mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_user(
    *,
    email="agent@example.com",
    role=UserRole.AGENT.value,
    is_active=True,
    failed_login_count=0,
    locked_until=None,
    password_hash=_HASHED_PW,
) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name="Support Agent",
        role=role,
        is_active=is_active,
        password_hash=password_hash,
        failed_login_count=failed_login_count,
        locked_until=locked_until,
    )
    return user


# ---- login tests ----


@pytest.mark.asyncio
async def test_login_unknown_email_raises_invalid_credentials():
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=None)

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            session,
            email="unknown@example.com",
            password=_PASSWORD,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_INVALID_CREDENTIALS"
    assert session.commit.await_count == 1
    # Verify audit row was added
    assert session.add.called
    audit_row = session.add.call_args[0][0]
    assert audit_row.action == "AUTH_LOGIN"
    assert audit_row.outcome == AuditOutcome.FAILURE.value
    assert audit_row.metadata_ == {"reason": "unknown_email"}


@pytest.mark.asyncio
async def test_login_inactive_user_raises_invalid_credentials():
    user = _make_user(is_active=False)
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=user)

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            session,
            email=user.email,
            password=_PASSWORD,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_INVALID_CREDENTIALS"
    assert session.commit.await_count == 1
    audit_row = session.add.call_args[0][0]
    assert audit_row.metadata_ == {"reason": "inactive"}


@pytest.mark.asyncio
async def test_login_locked_user_raises_account_locked(monkeypatch):
    locked_until = _NOW + timedelta(minutes=10)
    user = _make_user(locked_until=locked_until)
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=user)
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            session,
            email=user.email,
            password=_PASSWORD,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_ACCOUNT_LOCKED"
    audit_row = session.add.call_args[0][0]
    assert audit_row.metadata_ == {"reason": "account_locked"}


@pytest.mark.asyncio
async def test_login_wrong_password_below_threshold_increments_count(monkeypatch):
    user = _make_user(failed_login_count=1)
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=user)
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: Settings(_env_file=None, max_login_attempts=5, account_lock_minutes=15),
    )

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            session,
            email=user.email,
            password="WrongPassword!",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_INVALID_CREDENTIALS"
    assert user.failed_login_count == 2
    assert user.locked_until is None


@pytest.mark.asyncio
async def test_login_wrong_password_at_threshold_locks_account(monkeypatch):
    user = _make_user(failed_login_count=4)
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=user)
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: Settings(_env_file=None, max_login_attempts=5, account_lock_minutes=15),
    )

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            session,
            email=user.email,
            password="WrongPassword!",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_ACCOUNT_LOCKED"
    assert user.failed_login_count == 0
    assert user.locked_until == _NOW + timedelta(minutes=15)


@pytest.mark.asyncio
async def test_login_success_resets_counter_and_issues_tokens(monkeypatch):
    user = _make_user(failed_login_count=3)
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=user)
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: Settings(_env_file=None, refresh_token_expire_days=7),
    )

    result = await auth_service.login(
        session,
        email=user.email,
        password=_PASSWORD,
        ip_address="127.0.0.1",
        user_agent="pytest-client",
    )

    assert result.user == user
    assert user.failed_login_count == 0
    assert user.locked_until is None

    # Verify access token
    payload = security.decode_access_token(result.access_token)
    assert payload["sub"] == str(user.id)
    assert payload["role"] == user.role

    # Verify refresh token raw string
    assert len(result.refresh_token_raw) >= 43

    # Verify refresh token was persisted in DB
    added_objs = [call[0][0] for call in session.add.call_args_list]
    refresh_rows = [obj for obj in added_objs if isinstance(obj, RefreshToken)]
    assert len(refresh_rows) == 1
    stored_rf = refresh_rows[0]
    assert stored_rf.user_id == user.id
    assert stored_rf.token_hash == security.hash_refresh_token(result.refresh_token_raw)
    assert stored_rf.expires_at == _NOW + timedelta(days=7)


# ---- refresh_access tests ----


@pytest.mark.asyncio
async def test_refresh_access_missing_or_revoked_token_raises():
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=None)

    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_access(
            session,
            refresh_token_raw="non_existent_token_raw",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_access_expired_token_raises(monkeypatch):
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=_NOW - timedelta(seconds=1),
        revoked_at=None,
    )
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=token_row)

    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_access(
            session,
            refresh_token_raw="raw_token",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_access_inactive_user_raises(monkeypatch):
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    user = _make_user(is_active=False)
    token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="hash",
        expires_at=_NOW + timedelta(days=5),
        revoked_at=None,
    )
    session = _make_mock_session()
    # First execute for RefreshToken, second for User
    session.execute.side_effect = [
        _MockResult(scalar=token_row),
        _MockResult(scalar=user),
    ]

    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_access(
            session,
            refresh_token_raw="raw_token",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.error_code == "AUTH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_access_success(monkeypatch):
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    user = _make_user(is_active=True)
    token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="hash",
        expires_at=_NOW + timedelta(days=5),
        revoked_at=None,
    )
    session = _make_mock_session()
    session.execute.side_effect = [
        _MockResult(scalar=token_row),
        _MockResult(scalar=user),
    ]

    res_user, new_token = await auth_service.refresh_access(
        session,
        refresh_token_raw="raw_token",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert res_user == user
    payload = security.decode_access_token(new_token)
    assert payload["sub"] == str(user.id)
    assert payload["role"] == user.role
    assert token_row.user_agent == "pytest"
    assert session.commit.called


# ---- logout tests ----


@pytest.mark.asyncio
async def test_logout_revokes_token(monkeypatch):
    monkeypatch.setattr(auth_service, "_utcnow", lambda: _NOW)
    token_row = RefreshToken(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=_NOW + timedelta(days=5),
        revoked_at=None,
    )
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=token_row)

    await auth_service.logout(
        session,
        refresh_token_raw="raw_token",
        ip_address="127.0.0.1",
    )

    assert token_row.revoked_at == _NOW
    assert session.commit.called


@pytest.mark.asyncio
async def test_logout_idempotent_when_not_found():
    session = _make_mock_session()
    session.execute.return_value = _MockResult(scalar=None)

    # Must not raise
    await auth_service.logout(
        session,
        refresh_token_raw="non_existent",
        ip_address="127.0.0.1",
    )
    assert not session.commit.called
