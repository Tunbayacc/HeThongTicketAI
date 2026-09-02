from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse, UserOut
from app.services import auth_service

# No prefix: main.py mounts this router under /api/auth (mirrors health.py).
router = APIRouter(tags=["auth"])

_COOKIE_PATH = "/api/auth"  # refresh cookie only sent back to auth endpoints


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )


def _client_context(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=raw_token,
        max_age=auth_service.refresh_cookie_max_age_seconds(settings),
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,  # True only over HTTPS (NFR-SEC-05)
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.refresh_token_cookie_name,
        path=_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict:
    ip, user_agent = _client_context(request)
    result = await auth_service.login(
        session, email=payload.email, password=payload.password,
        ip_address=ip, user_agent=user_agent,
    )
    _set_refresh_cookie(response, result.refresh_token_raw)
    return {"access_token": result.access_token, "token_type": "bearer", "user": to_user_out(result.user)}


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    raw = request.cookies.get(get_settings().refresh_token_cookie_name)
    if not raw:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.")
    ip, user_agent = _client_context(request)
    user, access_token = await auth_service.refresh_access(
        session, refresh_token_raw=raw, ip_address=ip, user_agent=user_agent,
    )
    return {"access_token": access_token, "token_type": "bearer", "user": to_user_out(user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> None:
    raw = request.cookies.get(get_settings().refresh_token_cookie_name)
    ip, _ = _client_context(request)
    if raw:
        await auth_service.logout(session, refresh_token_raw=raw, ip_address=ip)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)) -> dict:
    return {"user": to_user_out(user)}
