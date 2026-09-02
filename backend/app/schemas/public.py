"""Public Portal request/response schemas. Only public, PII-the-customer-owns data
leaves this boundary (SRS FR-PUB-06/07); never internal notes, AI or assignment.
"""

from datetime import datetime

from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_CATEGORY_PATTERN = r"^(TECHNICAL|ACCOUNT|BILLING|GENERAL|OTHER)$"


class PortalCreateRequest(BaseModel):
    requester_name: str = Field(..., min_length=2, max_length=100)
    requester_email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN)
    subject: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=20000)
    category: str | None = Field(default=None, pattern=_CATEGORY_PATTERN)  # optional; NULL otherwise


class PortalTicketOut(BaseModel):
    ticket_code: str
    status: str
    subject: str
    created_at: datetime


class PortalCommentOut(BaseModel):
    id: str
    content: str
    created_at: datetime


class PortalTrackRequest(BaseModel):
    email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN)
    ticket_code: str = Field(..., min_length=3, max_length=30)


class PortalTrackResponse(BaseModel):
    ticket_code: str
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime
    comments: list[PortalCommentOut]
