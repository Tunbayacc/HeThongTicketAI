import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.ticket import SlaPolicy
from app.schemas.admin import SlaPolicyCreate, SlaPolicyUpdate
from app.services.audit import write_audit


def intervals_overlap(
    a_from: datetime, a_to: datetime | None,
    b_from: datetime, b_to: datetime | None,
) -> bool:
    """True if half-open intervals [a_from, a_to) and [b_from, b_to) overlap.

    None means +infinity.
    """
    # [start1, end1) and [start2, end2) overlap iff start1 < end2 and start2 < end1
    left = b_to is None or a_from < b_to
    right = a_to is None or b_from < a_to
    return left and right


async def list_policies(
    session: AsyncSession, *, priority: str | None = None, is_active: bool | None = None
) -> list[SlaPolicy]:
    conds = []
    if priority:
        conds.append(SlaPolicy.priority == priority)
    if is_active is not None:
        conds.append(SlaPolicy.is_active == is_active)

    query = select(SlaPolicy).where(*conds).order_by(SlaPolicy.priority.asc(), SlaPolicy.effective_from.desc())
    return (await session.execute(query)).scalars().all()


async def create_policy(
    session: AsyncSession, *, actor_id: uuid.UUID, payload: SlaPolicyCreate
) -> SlaPolicy:
    if payload.effective_to and payload.effective_to <= payload.effective_from:
        raise AppError(422, "VALIDATION_ERROR", "effective_to phải sau effective_from.")

    # Check overlap among active policies for this priority
    if payload.is_active:
        existing_active = (
            await session.execute(
                select(SlaPolicy).where(
                    SlaPolicy.priority == payload.priority,
                    SlaPolicy.is_active.is_(True),
                )
            )
        ).scalars().all()

        for ep in existing_active:
            if intervals_overlap(payload.effective_from, payload.effective_to, ep.effective_from, ep.effective_to):
                raise AppError(
                    409,
                    "SLA_POLICY_CONFLICT",
                    f"Chính sách SLA bị chồng lấn thời gian hiệu lực với '{ep.name}'.",
                )

    policy = SlaPolicy(
        name=payload.name.strip(),
        priority=payload.priority,
        first_response_minutes=payload.first_response_minutes,
        resolution_minutes=payload.resolution_minutes,
        pause_on_pending=payload.pause_on_pending,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        is_active=payload.is_active,
    )
    session.add(policy)
    await session.flush()

    await write_audit(
        session,
        action="SLA_POLICY_CREATED",
        entity_type="SLA_POLICY",
        entity_id=policy.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata={"name": policy.name, "priority": policy.priority},
    )
    await session.commit()
    await session.refresh(policy)
    return policy


async def update_policy(
    session: AsyncSession, *, actor_id: uuid.UUID, policy_id: uuid.UUID, payload: SlaPolicyUpdate
) -> SlaPolicy:
    policy = await session.get(SlaPolicy, policy_id)
    if not policy:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy chính sách SLA.")

    new_from = payload.effective_from or policy.effective_from
    new_to = payload.effective_to if payload.effective_to is not None else policy.effective_to
    new_active = payload.is_active if payload.is_active is not None else policy.is_active

    if new_to and new_to <= new_from:
        raise AppError(422, "VALIDATION_ERROR", "effective_to phải sau effective_from.")

    # If active, ensure no overlap with other active policies of the same priority
    if new_active:
        other_active = (
            await session.execute(
                select(SlaPolicy).where(
                    SlaPolicy.priority == policy.priority,
                    SlaPolicy.is_active.is_(True),
                    SlaPolicy.id != policy.id,
                )
            )
        ).scalars().all()

        for ep in other_active:
            if intervals_overlap(new_from, new_to, ep.effective_from, ep.effective_to):
                raise AppError(
                    409,
                    "SLA_POLICY_CONFLICT",
                    f"Chính sách SLA bị chồng lấn thời gian hiệu lực với '{ep.name}'.",
                )

    changes = {}
    if payload.name is not None:
        policy.name = payload.name.strip()
        changes["name"] = policy.name
    if payload.first_response_minutes is not None:
        policy.first_response_minutes = payload.first_response_minutes
        changes["first_response_minutes"] = policy.first_response_minutes
    if payload.resolution_minutes is not None:
        policy.resolution_minutes = payload.resolution_minutes
        changes["resolution_minutes"] = policy.resolution_minutes
    if payload.pause_on_pending is not None:
        policy.pause_on_pending = payload.pause_on_pending
        changes["pause_on_pending"] = policy.pause_on_pending
    if payload.effective_from is not None:
        policy.effective_from = payload.effective_from
        changes["effective_from"] = str(policy.effective_from)
    if payload.effective_to is not None:
        policy.effective_to = payload.effective_to
        changes["effective_to"] = str(policy.effective_to)
    if payload.is_active is not None:
        policy.is_active = payload.is_active
        changes["is_active"] = policy.is_active

    await write_audit(
        session,
        action="SLA_POLICY_UPDATED",
        entity_type="SLA_POLICY",
        entity_id=policy.id,
        actor_id=actor_id,
        outcome="SUCCESS",
        metadata=changes,
    )
    await session.commit()
    await session.refresh(policy)
    return policy
