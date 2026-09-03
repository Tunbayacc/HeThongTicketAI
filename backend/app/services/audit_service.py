from datetime import date, datetime, time, timezone
import math
import uuid
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit import AuditLog
from app.models.user import User


async def list_audit_logs(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    conds = []

    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if action:
        conds.append(AuditLog.action == action)
    if entity_type:
        conds.append(AuditLog.entity_type == entity_type)

    tz = ZoneInfo(get_settings().reporting_timezone)
    if from_date:
        dt_from = datetime.combine(from_date, time.min, tzinfo=tz).astimezone(timezone.utc)
        conds.append(AuditLog.created_at >= dt_from)
    if to_date:
        dt_to = datetime.combine(to_date, time.max, tzinfo=tz).astimezone(timezone.utc)
        conds.append(AuditLog.created_at <= dt_to)

    total = (await session.execute(select(func.count(AuditLog.id)).where(*conds))).scalar_one()

    # Join with User to attach actor_name
    query = (
        select(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.actor_id == User.id)
        .where(*conds)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(query)).all()

    items = []
    for log, actor_name in rows:
        d = {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_name": actor_name,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "outcome": log.outcome,
            "metadata_": log.metadata_,
            "ip_address": str(log.ip_address) if log.ip_address else None,
            "created_at": log.created_at,
        }
        items.append(d)

    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
