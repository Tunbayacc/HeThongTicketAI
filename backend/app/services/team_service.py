import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.team import SupportTeam, TeamMember
from app.models.user import User
from app.schemas.admin import MemberAdd, TeamCreate, TeamUpdate
from app.services.audit import write_audit


async def list_teams(session: AsyncSession, *, is_active: bool | None = None) -> list[dict]:
    conds = []
    if is_active is not None:
        conds.append(SupportTeam.is_active == is_active)

    teams = (
        await session.execute(
            select(SupportTeam)
            .where(*conds)
            .order_by(SupportTeam.name.asc())
        )
    ).scalars().all()

    # Count active members per team
    counts = dict(
        (
            await session.execute(
                select(TeamMember.team_id, func.count(TeamMember.id))
                .where(TeamMember.is_active.is_(True))
                .group_by(TeamMember.team_id)
            )
        ).all()
    )

    out = []
    for t in teams:
        d = {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "is_active": t.is_active,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "member_count": counts.get(t.id, 0),
        }
        out.append(d)
    return out


async def create_team(session: AsyncSession, *, actor_id: uuid.UUID, payload: TeamCreate) -> SupportTeam:
    name_clean = payload.name.strip()
    existing = (
        await session.execute(select(SupportTeam).where(func.lower(SupportTeam.name) == name_clean.lower()))
    ).scalar_one_or_none()
    if existing:
        raise AppError(409, "CONFLICT", f"Nhóm '{name_clean}' đã tồn tại.")

    team = SupportTeam(name=name_clean, description=payload.description)
    session.add(team)
    await session.flush()

    await write_audit(
        session,
        action="TEAM_CREATED",
        entity_type="TEAM",
        entity_id=team.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata={"name": team.name},
    )
    await session.commit()
    await session.refresh(team)
    return team


async def get_team_detail(session: AsyncSession, *, team_id: uuid.UUID) -> dict:
    team = await session.get(SupportTeam, team_id)
    if not team:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy nhóm.")

    members_query = (
        select(TeamMember, User)
        .join(User, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
        .order_by(TeamMember.joined_at.asc())
    )
    member_rows = (await session.execute(members_query)).all()

    members_list = []
    active_count = 0
    for tm, u in member_rows:
        if tm.is_active:
            active_count += 1
        members_list.append({
            "id": tm.id,
            "user_id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "user_role": u.role,
            "team_role": tm.team_role,
            "is_active": tm.is_active,
            "joined_at": tm.joined_at,
        })

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "is_active": team.is_active,
        "created_at": team.created_at,
        "updated_at": team.updated_at,
        "member_count": active_count,
        "members": members_list,
    }


async def update_team(
    session: AsyncSession, *, actor_id: uuid.UUID, team_id: uuid.UUID, payload: TeamUpdate
) -> SupportTeam:
    team = await session.get(SupportTeam, team_id)
    if not team:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy nhóm.")

    changes = {}
    if payload.name is not None and payload.name.strip().lower() != team.name.lower():
        name_clean = payload.name.strip()
        existing = (
            await session.execute(
                select(SupportTeam).where(
                    func.lower(SupportTeam.name) == name_clean.lower(),
                    SupportTeam.id != team.id,
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise AppError(409, "CONFLICT", f"Tên nhóm '{name_clean}' đã được sử dụng.")
        team.name = name_clean
        changes["name"] = team.name
    if payload.description is not None:
        team.description = payload.description
        changes["description"] = team.description
    if payload.is_active is not None:
        team.is_active = payload.is_active
        changes["is_active"] = team.is_active

    await write_audit(
        session,
        action="TEAM_UPDATED",
        entity_type="TEAM",
        entity_id=team.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata=changes,
    )
    await session.commit()
    await session.refresh(team)
    return team


async def add_team_member(
    session: AsyncSession, *, actor_id: uuid.UUID, team_id: uuid.UUID, payload: MemberAdd
) -> TeamMember:
    team = await session.get(SupportTeam, team_id)
    if not team:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy nhóm.")

    user = await session.get(User, payload.user_id)
    if not user:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy người dùng.")

    # FR-ADM-08: Không được thêm người dùng không hoạt động vào nhóm
    if not user.is_active:
        raise AppError(400, "BAD_REQUEST", "Không thể thêm người dùng không hoạt động vào nhóm.")

    membership = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == payload.user_id,
            )
        )
    ).scalar_one_or_none()

    if membership:
        membership.is_active = True
        membership.team_role = payload.team_role
    else:
        membership = TeamMember(
            team_id=team_id,
            user_id=payload.user_id,
            team_role=payload.team_role,
            is_active=True,
        )
        session.add(membership)

    await session.flush()
    await write_audit(
        session,
        action="TEAM_MEMBER_ADDED",
        entity_type="TEAM",
        entity_id=team_id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata={"user_id": str(user.id), "team_role": payload.team_role},
    )
    await session.commit()
    await session.refresh(membership)
    return membership


async def remove_team_member(
    session: AsyncSession, *, actor_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    membership = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if membership and membership.is_active:
        membership.is_active = False
        await write_audit(
            session,
            action="TEAM_MEMBER_REMOVED",
            entity_type="TEAM",
            entity_id=team_id,
            actor_id=actor_id,
            outcome="SUCCESS",
            metadata={"user_id": str(user_id)},
        )
        await session.commit()
