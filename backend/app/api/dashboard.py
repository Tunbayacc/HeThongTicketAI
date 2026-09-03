"""Dashboard HTTP API (SRS 8.5 / FR-REP) — role-scoped summary KPIs + trends.

Every staff role may read the dashboard (Task 3 widens dashboard scope to AGENT).
Each caller sees the exact Ticket List scope (FR-REP-11) aggregated server-side in
dashboard_service; the router is a thin alias/validation layer. An inverted range
(from > to) is a business rule and surfaces as the standard AppError envelope;
a malformed date string 422s through the shared RequestValidationError handler.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.errors import AppError
from app.db.session import get_session
from app.models.user import User
from app.schemas.dashboard import SummaryResponse, TrendsResponse
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])

DASHBOARD_ROLES = ("AGENT", "MANAGER", "ADMIN")


@router.get("/dashboard/summary", response_model=SummaryResponse)
async def dashboard_summary(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    user: User = Depends(require_roles(*DASHBOARD_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> SummaryResponse:
    try:
        return await dashboard_service.summary(
            session, user=user, from_date=from_date, to_date=to_date)
    except ValueError:
        raise AppError(422, "VALIDATION_ERROR", "Khoảng thời gian không hợp lệ.")


@router.get("/dashboard/trends", response_model=TrendsResponse)
async def dashboard_trends(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    user: User = Depends(require_roles(*DASHBOARD_ROLES)),
    session: AsyncSession = Depends(get_session),
) -> TrendsResponse:
    try:
        return await dashboard_service.trends(
            session, user=user, from_date=from_date, to_date=to_date)
    except ValueError:
        raise AppError(422, "VALIDATION_ERROR", "Khoảng thời gian không hợp lệ.")
