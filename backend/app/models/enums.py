from enum import Enum


class UserRole(str, Enum):
    AGENT = "AGENT"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


class TeamRole(str, Enum):
    MEMBER = "MEMBER"
    MANAGER = "MANAGER"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(str, Enum):
    TECHNICAL = "TECHNICAL"
    ACCOUNT = "ACCOUNT"
    BILLING = "BILLING"
    GENERAL = "GENERAL"
    OTHER = "OTHER"


class Visibility(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"


class CommentSource(str, Enum):
    HUMAN = "HUMAN"
    AI_ASSISTED = "AI_ASSISTED"


class AiResultType(str, Enum):
    CLASSIFICATION = "CLASSIFICATION"
    SUMMARY = "SUMMARY"
    DRAFT_REPLY = "DRAFT_REPLY"


class AiStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AuditOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
