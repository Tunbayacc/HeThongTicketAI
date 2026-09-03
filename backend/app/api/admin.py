import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.db.session import get_session
from app.models.user import User
from app.schemas.admin import (
    MemberAdd,
    PaginatedUsers,
    TeamCreate,
    TeamDetailOut,
    TeamOut,
    TeamUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services import team_service, user_service

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


# --- Teams & Members ---


@router.post("/teams", response_model=TeamOut, status_code=201)
async def create_team(
    payload: TeamCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    t = await team_service.create_team(session, actor_id=current_user.id, payload=payload)
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "is_active": t.is_active,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "member_count": 0,
    }


@router.get("/teams/{team_id}", response_model=TeamDetailOut)
async def get_team(
    team_id: uuid.UUID,
    _: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    return await team_service.get_team_detail(session, team_id=team_id)


@router.patch("/teams/{team_id}", response_model=TeamDetailOut)
async def update_team(
    team_id: uuid.UUID,
    payload: TeamUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    await team_service.update_team(
        session, actor_id=current_user.id, team_id=team_id, payload=payload
    )
    return await team_service.get_team_detail(session, team_id=team_id)


@router.post("/teams/{team_id}/members", status_code=200)
async def add_team_member(
    team_id: uuid.UUID,
    payload: MemberAdd,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    await team_service.add_team_member(
        session, actor_id=current_user.id, team_id=team_id, payload=payload
    )
    return {"message": "Thêm thành viên thành công."}


@router.delete("/teams/{team_id}/members/{user_id}", status_code=204)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(require_roles("ADMIN")),
    session: AsyncSession = Depends(get_session),
):
    await team_service.remove_team_member(
        session, actor_id=current_user.id, team_id=team_id, user_id=user_id
    )
