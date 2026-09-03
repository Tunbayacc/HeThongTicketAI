import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin import PaginatedUsers, UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    q: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.list_users(
        session, q=q, role=role, is_active=is_active, page=page, page_size=page_size
    )


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.create_user(session, actor_id=current_user.id, payload=payload)


@router.get("/users/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.get_user(session, user_id=user_id)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    return await user_service.update_user(
        session, actor_id=current_user.id, user_id=user_id, payload=payload
    )
