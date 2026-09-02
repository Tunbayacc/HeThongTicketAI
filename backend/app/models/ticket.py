import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.models.base import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    priority = Column(String(30), nullable=False)  # LOW/MEDIUM/HIGH/URGENT
    first_response_minutes = Column(Integer, nullable=False)
    resolution_minutes = Column(Integer, nullable=False)
    pause_on_pending = Column(Boolean, nullable=False, server_default=text("false"))
    effective_from = Column(DateTime(timezone=True), nullable=False)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint(
            "first_response_minutes > 0",
            name="sla_first_response_positive",
        ),
        CheckConstraint(
            "resolution_minutes > 0",
            name="sla_resolution_positive",
        ),
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_updated", "status", "updated_at"),
        Index("ix_tickets_team_status_updated", "team_id", "status", "updated_at"),
        Index("ix_tickets_assigned_status_updated", "assigned_to", "status", "updated_at"),
        Index("ix_tickets_priority_resolution_due", "priority", "resolution_due_at"),
        Index("ix_tickets_requester_email", "requester_email"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique constraint (implicit unique index) satisfies SRS 6.5 tickets(ticket_code).
    ticket_code = Column(String(30), nullable=False, unique=True)
    requester_name = Column(String(100), nullable=False)
    requester_email = Column(String(255), nullable=False)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)  # TECHNICAL/ACCOUNT/BILLING/GENERAL/OTHER
    priority = Column(String(30), nullable=False)  # LOW/MEDIUM/HIGH/URGENT
    status = Column(String(30), nullable=False)  # OPEN/IN_PROGRESS/PENDING/RESOLVED/CLOSED
    team_id = Column(
        Uuid(as_uuid=True), ForeignKey("support_teams.id"), nullable=True, index=True
    )
    assigned_to = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    sla_policy_id = Column(
        Uuid(as_uuid=True), ForeignKey("sla_policies.id"), nullable=True
    )
    first_response_due_at = Column(DateTime(timezone=True), nullable=True)
    resolution_due_at = Column(DateTime(timezone=True), nullable=True)
    first_response_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    comments = relationship("Comment", back_populates="ticket", lazy="selectin")
    attachments = relationship("Attachment", back_populates="ticket", lazy="selectin")
    history = relationship("TicketHistory", back_populates="ticket", lazy="selectin")
    ai_results = relationship("AiResult", back_populates="ticket", lazy="selectin")


class AiResult(Base):
    __tablename__ = "ai_results"
    __table_args__ = (
        Index(
            "ix_ai_results_ticket_type_status_requested",
            "ticket_id",
            "result_type",
            "status",
            "requested_at",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    requested_by = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    result_type = Column(String(30), nullable=False)  # CLASSIFICATION/SUMMARY/DRAFT_REPLY
    status = Column(String(30), nullable=False)  # PENDING_REVIEW/APPROVED/EDITED/REJECTED/FAILED
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(30), nullable=False)
    input_hash = Column(String(128), nullable=False)
    context_cutoff_at = Column(DateTime(timezone=True), nullable=True)
    original_output = Column(JSONB, nullable=True)
    reviewed_output = Column(JSONB, nullable=True)
    confidence = Column(Numeric(4, 3), nullable=True)
    reviewer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_reason = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)

    ticket = relationship("Ticket", back_populates="ai_results")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_ticket_created", "ticket_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    content = Column(Text, nullable=False)
    visibility = Column(String(30), nullable=False)  # PUBLIC/INTERNAL
    source = Column(String(30), nullable=False)  # HUMAN/AI_ASSISTED
    ai_result_id = Column(
        Uuid(as_uuid=True), ForeignKey("ai_results.id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    comment_id = Column(
        Uuid(as_uuid=True), ForeignKey("comments.id"), nullable=True
    )
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False, unique=True)
    storage_path = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    checksum = Column(String(128), nullable=True)
    uploaded_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    ticket = relationship("Ticket", back_populates="attachments")


class TicketHistory(Base):
    __tablename__ = "ticket_history"
    __table_args__ = (
        Index("ix_ticket_history_ticket_created", "ticket_id", "created_at"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        Uuid(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    changed_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # STATUS_CHANGED/ASSIGNED/FIELD_UPDATED/...
    field_name = Column(String(50), nullable=True)
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    ticket = relationship("Ticket", back_populates="history")
