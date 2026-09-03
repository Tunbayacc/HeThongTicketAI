"""Dashboard HTTP response schemas (SRS 8.5 / FR-REP). Wire keys stay from/to
as in the API contract; Python attribute names never collide with keywords.
populate_by_name lets the service dicts (already keyed from/to) validate through
the aliases, and FastAPI serializes by alias so the JSON keeps from/to."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RangeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    timezone: str
    granularity: Literal["day", "month"]


class KpiOut(BaseModel):
    total: int
    by_status: dict[str, int]  # exactly the 5 status keys, 0-filled


class SlaOut(BaseModel):
    tracked: int
    on_time: int
    due_soon: int
    overdue: int


class SummaryResponse(BaseModel):
    range: RangeOut
    kpi: KpiOut
    sla: SlaOut
    avg_first_response_seconds: int | None
    avg_resolution_seconds: int | None


class TrendBucketOut(BaseModel):
    bucket: str  # "YYYY-MM-DD" | "YYYY-MM"
    statuses: dict[str, int]  # exactly the 5 status keys, 0-filled


class TrendsResponse(BaseModel):
    range: RangeOut
    buckets: list[TrendBucketOut]
