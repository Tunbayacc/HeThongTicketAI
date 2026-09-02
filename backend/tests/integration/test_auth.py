"""Integration: auth service flow against the real DB (S1 design spec 10: Test).

Run with the S0 acceptance stack up and:
  DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5433/ai_support INTEGRATION=1

Each test creates its own user (role AGENT) and deletes it afterwards so the
seeded demo accounts (admin/manager/agent) are never modified or locked.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.core.security import decode_access_token, hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.enums import AuditOutcome, UserRole
from app.models.user import RefreshToken, User
from app.services import auth_service

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()  # drop pooled connections so the next test's loop is clean


async def _create_agent() -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            full_name="Integration Tester",
            email=f"it.auth.{uuid.uuid4().hex[:12]}@example.com",
            password_hash=hash_password("Test@123456"),
            role=UserRole.AGENT.value,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _cleanup_user(user_id) -> None:
    async with AsyncSessionLocal() as session:
        # audit_logs.actor_id has no ON DELETE CASCADE -> delete our rows first.
        await session.execute(
            delete(AuditLog).where((AuditLog.actor_id == user_id) | (AuditLog.entity_id == user_id))
        )
        await session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_login_success_issues_tokens_and_audits():
    user = await _create_agent()
    try:
        async with AsyncSessionLocal() as session:
            result = await auth_service.login(
                session, email=user.email.upper(),  # normalisation is exercised
                password="Test@123456", ip_address="203.0.113.5", user_agent="pytest",
            )
            assert result.user.id == user.id

            payload = decode_access_token(result.access_token)
            assert payload["sub"] == str(user.id)
            assert payload["role"] == "AGENT"

            rows = (
                await session.execute(select(RefreshToken).where(RefreshToken.user_id == user.id))
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].token_hash != result.refresh_token_raw  # stored hashed
            assert rows[0].expires_at > datetime.now(timezone.utc)
            assert str(rows[0].ip_address) == "203.0.113.5"  # asyncpg returns IPv4Address for INET

            audit_count = (
                await session.execute(
                    select(func.count(AuditLog.id)).where(
                        AuditLog.actor_id == user.id,
                        AuditLog.action == "AUTH_LOGIN",
                        AuditLog.outcome == AuditOutcome.SUCCESS.value,
                    )
                )
            ).scalar_one()
            assert audit_count >= 1
    finally:
        await _cleanup_user(user.id)


async def test_wrong_password_increments_then_locks_account():
    user = await _create_agent()
    try:
        for _ in range(4):
            with pytest.raises(AppError) as exc:
                async with AsyncSessionLocal() as session:
                    await auth_service.login(
                        session, email=user.email, password="wrong-pass", ip_address=None, user_agent=None,
                    )
            assert exc.value.error_code == "AUTH_INVALID_CREDENTIALS"

        with pytest.raises(AppError) as fifth:
            async with AsyncSessionLocal() as session:
                await auth_service.login(
                    session, email=user.email, password="wrong-pass", ip_address=None, user_agent=None,
                )
        assert fifth.value.error_code == "AUTH_ACCOUNT_LOCKED"

        # Even the correct password is refused while the lock is active.
        with pytest.raises(AppError) as locked:
            async with AsyncSessionLocal() as session:
                await auth_service.login(
                    session, email=user.email, password="Test@123456", ip_address=None, user_agent=None,
                )
        assert locked.value.error_code == "AUTH_ACCOUNT_LOCKED"
    finally:
        await _cleanup_user(user.id)


async def test_refresh_then_logout_revokes_token():
    user = await _create_agent()
    try:
        async with AsyncSessionLocal() as session:
            result = await auth_service.login(
                session, email=user.email, password="Test@123456", ip_address=None, user_agent=None,
            )
            refreshed_user, new_access = await auth_service.refresh_access(
                session, refresh_token_raw=result.refresh_token_raw, ip_address=None, user_agent=None,
            )
            assert refreshed_user.id == user.id
            assert new_access != result.access_token
            await auth_service.logout(session, refresh_token_raw=result.refresh_token_raw, ip_address=None)

        with pytest.raises(AppError) as rejected:
            async with AsyncSessionLocal() as session:
                await auth_service.refresh_access(
                    session, refresh_token_raw=result.refresh_token_raw, ip_address=None, user_agent=None,
                )
        assert rejected.value.error_code == "AUTH_TOKEN_EXPIRED"
    finally:
        await _cleanup_user(user.id)
