"""Staff authentication service: bcrypt verify, lockout, access + refresh issuance.

Pure policy helpers are module-level functions so the security math is
unit-testable without a DB (SRS FR-AUTH, NFR-SEC; design spec §5.3).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.enums import AuditOutcome
from app.models.user import RefreshToken, User
from app.services.audit import coerce_ip, write_audit

LOGIN_ACTION = "AUTH_LOGIN"
LOGOUT_ACTION = "AUTH_LOGOUT"
ENTITY_USER = "user"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- pure, unit-testable policy helpers -------------------------------------


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_locked(locked_until: datetime | None, *, now: datetime | None = None) -> bool:
    """A lock is active only strictly after its expiry instant (FR-AUTH-08)."""
    return locked_until is not None and locked_until > (now or _utcnow())


@dataclass(frozen=True)
class LoginFailureState:
    failed_login_count: int
    locked_until: datetime | None
    lock_triggered: bool


def next_failure_state(
    *,
    failed_login_count: int,
    max_attempts: int,
    lock_minutes: int,
    now: datetime,
) -> LoginFailureState:
    """Increment the failure counter; on reaching max_attempts, lock the account.

    The counter resets to 0 on lock so the account gets a full fresh window once
    the lock expires. Pure so the threshold maths are unit-testable.
    """
    count = failed_login_count + 1
    if count >= max_attempts:
        return LoginFailureState(0, now + timedelta(minutes=lock_minutes), lock_triggered=True)
    return LoginFailureState(count, None, lock_triggered=False)


def refresh_cookie_max_age_seconds(settings: Settings) -> int:
    return settings.refresh_token_expire_days * 86400


# ---- service functions -------------------------------------------------------


@dataclass
class LoginSuccess:
    user: User
    access_token: str
    refresh_token_raw: str


async def _store_refresh_token(
    session: AsyncSession, *, user: User, now: datetime, ip_address: str | None, user_agent: str | None
) -> str:
    settings = get_settings()
    raw = generate_refresh_token()  # >= 256 bits entropy (NFR-SEC-04)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),  # stored hashed, never the raw value
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent,
            ip_address=coerce_ip(ip_address),
        )
    )
    return raw


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> LoginSuccess:
    settings = get_settings()
    now = _utcnow()
    user = (
        await session.execute(select(User).where(User.email == normalize_email(email)))
    ).scalar_one_or_none()

    # Unknown email, inactive account and wrong password share ONE message and code
    # so the response never confirms whether an email exists (UC-01, FR-AUTH-02).
    if user is None:
        await write_audit(
            session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.FAILURE.value,
            metadata={"reason": "unknown_email"}, ip_address=ip_address,
        )
        await session.commit()
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.")

    if not user.is_active:
        await write_audit(
            session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.FAILURE.value,
            actor_id=user.id, entity_id=user.id, metadata={"reason": "inactive"}, ip_address=ip_address,
        )
        await session.commit()
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.")

    if is_locked(user.locked_until, now=now):
        await write_audit(
            session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.FAILURE.value,
            actor_id=user.id, entity_id=user.id, metadata={"reason": "account_locked"}, ip_address=ip_address,
        )
        await session.commit()
        raise AppError(401, "AUTH_ACCOUNT_LOCKED",
                       "Tài khoản đã bị khóa tạm thời do đăng nhập sai nhiều lần. Vui lòng thử lại sau ít phút.")

    if not verify_password(password, user.password_hash):
        state = next_failure_state(
            failed_login_count=user.failed_login_count,
            max_attempts=settings.max_login_attempts,
            lock_minutes=settings.account_lock_minutes,
            now=now,
        )
        user.failed_login_count = state.failed_login_count
        user.locked_until = state.locked_until
        await write_audit(
            session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.FAILURE.value,
            actor_id=user.id, entity_id=user.id,
            metadata={"reason": "account_locked" if state.lock_triggered else "invalid_credentials"},
            ip_address=ip_address,
        )
        await session.commit()
        if state.lock_triggered:
            raise AppError(401, "AUTH_ACCOUNT_LOCKED",
                           "Tài khoản đã bị khóa tạm thời do đăng nhập sai nhiều lần. Vui lòng thử lại sau ít phút.")
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng.")

    # Success: reset lock state and issue both tokens (FR-AUTH-04/05).
    user.failed_login_count = 0
    user.locked_until = None
    access_token = create_access_token(user_id=str(user.id), role=user.role)
    raw_refresh = await _store_refresh_token(session, user=user, now=now, ip_address=ip_address, user_agent=user_agent)
    await write_audit(
        session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.SUCCESS.value,
        actor_id=user.id, entity_id=user.id, metadata={"method": "password"}, ip_address=ip_address,
    )
    await session.commit()
    return LoginSuccess(user=user, access_token=access_token, refresh_token_raw=raw_refresh)


async def refresh_access(
    session: AsyncSession,
    *,
    refresh_token_raw: str,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[User, str]:
    """Mint a fresh access token from a live refresh token (FR-AUTH-06).

    Missing, revoked, expired or user-now-inactive all surface as 401
    AUTH_TOKEN_EXPIRED — from the client's point of view the session is simply
    over and it should go to /login.
    """
    now = _utcnow()
    token_hash = hash_refresh_token(refresh_token_raw)
    row = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    if row is None or row.expires_at <= now:
        await write_audit(
            session, action=LOGIN_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.FAILURE.value,
            metadata={"reason": "refresh_rejected"}, ip_address=ip_address,
        )
        await session.commit()
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")

    user = (await session.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Phiên đăng nhập không còn hiệu lực, vui lòng đăng nhập lại.")

    row.user_agent = user_agent
    row.ip_address = coerce_ip(ip_address)
    await session.commit()
    return user, create_access_token(user_id=str(user.id), role=user.role)


async def logout(session: AsyncSession, *, refresh_token_raw: str, ip_address: str | None) -> None:
    """Revoke the refresh token (FR-AUTH-07). Idempotent: unknown token is a no-op."""
    now = _utcnow()
    row = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh_token_raw),
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return
    row.revoked_at = now
    await write_audit(
        session, action=LOGOUT_ACTION, entity_type=ENTITY_USER, outcome=AuditOutcome.SUCCESS.value,
        actor_id=row.user_id, entity_id=row.user_id, ip_address=ip_address,
    )
    await session.commit()
