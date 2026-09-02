"""Pydantic IO models for the AI engine (SRS 8.4 / design spec 7.4).

Request models are deliberately thin — the service re-validates reviewed_output
against the per-type OUTPUT_SCHEMAS. AiResultOut carries the DERIVED
low_confidence flag (confidence < ai_low_confidence_threshold on CLASSIFICATION
rows); it is never stored. Field names stay English; labels.js owns Vietnamese
display.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AiResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    result_type: str  # CLASSIFICATION/SUMMARY/DRAFT_REPLY
    status: str  # PENDING_REVIEW/APPROVED/EDITED/REJECTED/FAILED
    model_name: str
    prompt_version: str
    input_hash: str
    confidence: float | None = None
    low_confidence: bool = False  # derived at read time, never stored
    original_output: dict | None = None
    reviewed_output: dict | None = None
    review_reason: str | None = None
    error_code: str | None = None
    context_cutoff_at: datetime | None = None
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    reviewed_at: datetime | None = None
    latency_ms: int | None = None
    requested_by: str | None = None
    reviewer_id: str | None = None


class AiResultListResponse(BaseModel):
    items: list[AiResultOut]
    total: int
    page: int
    page_size: int


class DraftGenerationRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=1000)


class ApproveRequest(BaseModel):
    version: int | None = None  # optimistic lock for CLASSIFICATION applies
    reason: str | None = Field(default=None, max_length=500)


class EditRequest(BaseModel):
    reviewed_output: dict  # validated against OUTPUT_SCHEMAS[result_type] in the service
    version: int | None = None
    reason: str | None = Field(default=None, max_length=500)


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
