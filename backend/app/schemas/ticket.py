"""Staff ticket schemas (SRS 8.2, 10.1). 'version' is the optimistic-lock guard:
a write body must echo the version it read, else the service returns 409
VERSION_CONFLICT (SRS 10.2)."""

from datetime import datetime

from pydantic import BaseModel, Field


class TicketListItem(BaseModel):
    id: str
    ticket_code: str
    subject: str
    category: str | None
    priority: str
    status: str
    requester_name: str
    requester_email: str
    team_id: str | None
    assigned_to: str | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int


class TicketListResponse(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class CommentOut(BaseModel):
    id: str
    author_id: str | None
    author_name: str | None  # staff full name; None => customer-authored
    content: str
    visibility: str  # PUBLIC | INTERNAL
    source: str      # HUMAN | AI_ASSISTED
    created_at: datetime
    edited_at: datetime | None


class AttachmentOut(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    uploaded_by: str | None


class HistoryOut(BaseModel):
    id: str
    event_type: str  # STATUS_CHANGED | ASSIGNED | FIELD_UPDATED
    field_name: str | None
    old_value: dict | str | None
    new_value: dict | str | None
    changed_by: str | None
    reason: str | None
    created_at: datetime


class TeamMemberOut(BaseModel):
    id: str
    full_name: str
    team_role: str  # MANAGER | MEMBER


class TeamOut(BaseModel):
    id: str
    name: str
    members: list[TeamMemberOut]


class TicketDetail(BaseModel):
    id: str
    ticket_code: str
    requester_name: str
    requester_email: str
    subject: str
    description: str
    category: str | None
    priority: str
    status: str
    team_id: str | None
    assigned_to: str | None
    sla_policy_id: str | None
    first_response_due_at: datetime | None
    resolution_due_at: datetime | None
    first_response_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    comments: list[CommentOut]
    attachments: list[AttachmentOut]
    history: list[HistoryOut]


class TicketUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=20000)
    category: str | None = Field(default=None, pattern=r"^(TECHNICAL|ACCOUNT|BILLING|GENERAL|OTHER)$")
    priority: str | None = Field(default=None, pattern=r"^(LOW|MEDIUM|HIGH|URGENT)$")
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(OPEN|IN_PROGRESS|PENDING|RESOLVED|CLOSED)$")
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)


class AssignRequest(BaseModel):
    team_id: str = Field(..., min_length=1)
    assigned_to: str | None = None
    reason: str | None = Field(default=None, max_length=2000)
    version: int = Field(..., ge=1)
