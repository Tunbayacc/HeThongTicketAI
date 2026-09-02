"""Auth dependencies: get_current_user (JWT) + RBAC gates + feature scope builder.

Design spec 5.1: every protected endpoint depends on get_current_user and the
relevant role/scope check; insufficient role -> 403 ACCESS_DENIED (AC-SEC-02).
"""

import uuid

import jwt as pyjwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)

# Feature -> allowed roles. S2 ticket listing and S5 dashboard scope their SQL
# through role_has_scope before composing queries (NFR-SEC-06).
_FEATURE_SCOPES: dict[str, set[str]] = {
    "tickets": {"AGENT", "MANAGER", "ADMIN"},
    "dashboard": {"MANAGER", "ADMIN"},
    "admin": {"ADMIN"},
}


def assert_allowed_role(user_role: str, allowed: tuple[str, ...]) -> None:
    """Pure RBAC gate: raise 403 ACCESS_DENIED unless user_role is in allowed."""
    if user_role not in allowed:
        raise AppError(403, "ACCESS_DENIED", "Bạn không có quyền truy cập chức năng này.")


def role_has_scope(role: str, feature: str) -> bool:
    """Pure scope check: can `role` access `feature`? Unknown features are denied."""
    return role in _FEATURE_SCOPES.get(feature, set())


def _unauthorized(message: str) -> AppError:
    # One stable code for every unusable-token case; the FE treats any 401 as
    # "session expired, try refresh once" (SRS 10.2 AUTH_TOKEN_EXPIRED).
    return AppError(401, "AUTH_TOKEN_EXPIRED", message)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Vui lòng đăng nhập.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError, KeyError, ValueError):
        raise _unauthorized("Phiên đăng nhập hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại.")
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _unauthorized("Phiên đăng nhập không còn hiệu lực. Vui lòng đăng nhập lại.")
    return user


def require_roles(*roles: str):
    """RBAC dependency factory: e.g. require_roles('MANAGER', 'ADMIN')."""

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        assert_allowed_role(user.role, roles)
        return user

    return _dependency
