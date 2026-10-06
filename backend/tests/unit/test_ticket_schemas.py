"""Unit tests for Pydantic request/response schemas in app.schemas.

Verifies field constraints, regex patterns, optimistic lock version guards,
and error handling when invalid inputs are provided.
"""

import pytest
from pydantic import ValidationError

from app.schemas.ai import (
    ApproveRequest,
    DraftGenerationRequest,
    EditRequest,
    RejectRequest,
)
from app.schemas.public import (
    PortalCreateRequest,
    PortalTrackRequest,
)
from app.schemas.ticket import (
    AssignRequest,
    StatusUpdateRequest,
    TicketUpdateRequest,
)


# ---- Portal Requests ----


def test_portal_create_request_valid():
    req = PortalCreateRequest(
        requester_name="Nguyen Van A",
        requester_email="user@example.com",
        subject="Khong the dang nhap",
        description="He thong bao loi sai mat khau mac du da doi pass.",
        category="ACCOUNT",
    )
    assert req.requester_name == "Nguyen Van A"
    assert req.category == "ACCOUNT"


def test_portal_create_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        PortalCreateRequest(
            requester_name="Nguyen Van A",
            requester_email="invalid-email-format",
            subject="Khong the dang nhap",
            description="Mo ta loi day du chi tiet.",
        )


def test_portal_create_request_rejects_short_name_or_subject():
    with pytest.raises(ValidationError):
        PortalCreateRequest(
            requester_name="A",  # min_length=2
            requester_email="user@example.com",
            subject="Loi",     # min_length=5
            description="Mo ta loi hop le va day du.",
        )


def test_portal_create_request_rejects_invalid_category():
    with pytest.raises(ValidationError):
        PortalCreateRequest(
            requester_name="Nguyen Van A",
            requester_email="user@example.com",
            subject="Tieu de hop le",
            description="Mo ta hop le va du ky tu quy dinh.",
            category="UNKNOWN_CATEGORY",
        )


def test_portal_track_request_valid_and_invalid():
    req = PortalTrackRequest(email="user@example.com", ticket_code="TK-12345678")
    assert req.ticket_code == "TK-12345678"

    with pytest.raises(ValidationError):
        PortalTrackRequest(email="bad-email", ticket_code="TK-12345678")

    with pytest.raises(ValidationError):
        PortalTrackRequest(email="user@example.com", ticket_code="TK")  # min_length=3


# ---- Ticket Staff Requests ----


def test_ticket_update_request_requires_positive_version():
    with pytest.raises(ValidationError):
        TicketUpdateRequest(subject="Tieu de moi", version=0)  # ge=1

    with pytest.raises(ValidationError):
        TicketUpdateRequest(subject="Tieu de moi")  # version is required

    req = TicketUpdateRequest(
        subject="Tieu de hop le",
        category="TECHNICAL",
        priority="URGENT",
        version=2,
    )
    assert req.version == 2
    assert req.category == "TECHNICAL"


def test_ticket_update_request_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        TicketUpdateRequest(priority="SUPER_HIGH", version=1)


def test_status_update_request_validation():
    req = StatusUpdateRequest(status="IN_PROGRESS", version=1, reason="Bat dau xu ly")
    assert req.status == "IN_PROGRESS"

    with pytest.raises(ValidationError):
        StatusUpdateRequest(status="NON_EXISTENT_STATUS", version=1)

    with pytest.raises(ValidationError):
        StatusUpdateRequest(status="RESOLVED")  # Missing version


def test_assign_request_validation():
    req = AssignRequest(team_id="team-uuid", assigned_to="user-uuid", version=1)
    assert req.team_id == "team-uuid"
    assert req.assigned_to == "user-uuid"

    with pytest.raises(ValidationError):
        AssignRequest(team_id="", version=1)  # Empty team_id disallowed

    with pytest.raises(ValidationError):
        AssignRequest(team_id="team-uuid")  # Missing version


# ---- AI Requests ----


def test_draft_generation_request_length_guard():
    req = DraftGenerationRequest(instruction="Viet cau tra loi ngan gon, lich su")
    assert req.instruction is not None

    with pytest.raises(ValidationError):
        DraftGenerationRequest(instruction="A" * 1001)  # max_length=1000


def test_ai_review_requests_validation():
    app_req = ApproveRequest(version=1, reason="Hop le")
    assert app_req.version == 1

    edit_req = EditRequest(reviewed_output={"category": "BILLING", "priority": "HIGH"}, version=2)
    assert edit_req.reviewed_output["category"] == "BILLING"

    rej_req = RejectRequest(reason="Khong dung noi dung")
    assert rej_req.reason == "Khong dung noi dung"
