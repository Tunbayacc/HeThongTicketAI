"""Validated shapes of model output (SRS 8.4). category/priority sit on the business
allowlist (same regexes as schemas/ticket.py) so BR-11 never lets a structurally
invalid AI proposal reach a ticket."""

from pydantic import BaseModel, Field

_CATEGORY = r"^(TECHNICAL|ACCOUNT|BILLING|GENERAL|OTHER)$"
_PRIORITY = r"^(LOW|MEDIUM|HIGH|URGENT)$"


class ClassificationOutput(BaseModel):
    category: str = Field(pattern=_CATEGORY)
    priority: str = Field(pattern=_PRIORITY)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=500)


class SummaryOutput(BaseModel):
    problem: str = Field(min_length=1, max_length=2000)
    key_points: list[str] = Field(min_length=1, max_length=20)
    actions_taken: list[str] = Field(default_factory=list, max_length=30)
    current_status: str = Field(min_length=1, max_length=500)
    next_steps: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class DraftOutput(BaseModel):
    draft: str = Field(min_length=1, max_length=10000)
    tone: str = Field(default="", max_length=200)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=10)


OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "CLASSIFICATION": ClassificationOutput,
    "SUMMARY": SummaryOutput,
    "DRAFT_REPLY": DraftOutput,
}
