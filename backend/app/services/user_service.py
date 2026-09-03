import math
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.admin import UserCreate, UserUpdate
from app.services.audit import write_audit


async def list_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    conds = []
    if q:
        kw = f"%{q.strip().lower()}%"
        conds.append(or_(func.lower(User.full_name).like(kw), func.lower(User.email).like(kw)))
    if role:
        conds.append(User.role == role)
    if is_active is not None:
        conds.append(User.is_active == is_active)

    total = (await session.execute(select(func.count(User.id)).where(*conds))).scalar_one()
    query = (
        select(User)
        .where(*conds)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await session.execute(query)).scalars().all()
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def create_user(session: AsyncSession, *, actor_id: uuid.UUID, payload: UserCreate) -> User:
    email_clean = payload.email.strip().lower()
    existing = (
        await session.execute(select(User).where(func.lower(User.email) == email_clean))
    ).scalar_one_or_none()
    if existing:
        raise AppError(409, "CONFLICT", f"Email '{email_clean}' đã được sử dụng.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email_clean,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    await write_audit(
        session,
        action="USER_CREATED",
        entity_type="USER",
        entity_id=user.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata={"role": user.role, "full_name": user.full_name},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, *, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy người dùng.")
    return user


async def update_user(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, payload: UserUpdate
) -> User:
    user = await get_user(session, user_id=user_id)
    changes = {}

    # Check last admin protection
    is_demoting_or_deactivating = (
        (payload.is_active is False and user.is_active is True)
        or (payload.role and payload.role != UserRole.ADMIN.value and user.role == UserRole.ADMIN.value)
    )
    if user.role == UserRole.ADMIN.value and is_demoting_or_deactivating:
        active_admin_count = (
            await session.execute(
                select(func.count(User.id)).where(
                    User.role == UserRole.ADMIN.value,
                    User.is_active.is_(True),
                    User.id != user.id,
                )
            )
        ).scalar_one()
        if active_admin_count == 0:
            raise AppError(400, "BAD_REQUEST", "Không thể vô hiệu hóa hoặc hạ quyền quản trị viên cuối cùng.")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
        changes["full_name"] = user.full_name
    if payload.role is not None:
        changes["old_role"] = user.role
        user.role = payload.role
        changes["new_role"] = user.role
    if payload.is_active is not None:
        changes["is_active"] = payload.is_active
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        changes["password_changed"] = True

    await write_audit(
        session,
        action="USER_UPDATED",
        entity_type="USER",
        entity_id=user.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata=changes,
    )
    await session.commit()
    await session.refresh(user)
    return user
