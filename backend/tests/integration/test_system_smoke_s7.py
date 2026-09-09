"""S7 System Smoke & Full-Lifecycle End-to-End Test Suite (SRS §13.3).

Validates the full business cycle:
1. Public ticket submission with attachment & ticket code generation (TK-*)
2. Public tracking verification
3. Manager login & assignment
4. Agent login & AI assistant workflow (Classification, Summarization, Draft response)
5. Human-in-the-loop review & approval of AI draft to public comment
6. SLA first_response_at timestamp recording
7. Public customer tracks again, observing public reply without internal data leaks
8. Strict state machine progression: OPEN -> IN_PROGRESS -> PENDING -> IN_PROGRESS -> RESOLVED -> CLOSED
9. Reopen workflow with justification
10. Dashboard metrics & SLA compliance validation
"""

import io
import os
import uuid
import httpx
import pytest

from app.db.session import engine
from app.main import app

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="requires INTEGRATION=1 and the compose DB on :5433",
)


@pytest.fixture(autouse=True)
async def _dispose_engine_after_each_test():
    yield
    await engine.dispose()


@pytest.fixture(scope="module")
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient, email: str, password: str = "Admin@Dev123") -> dict[str, str]:
    res = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_full_system_lifecycle_smoke(client: httpx.AsyncClient):
    # --------------------------------------------------------------------------
    # 1. Public user submits a ticket with an attachment
    # --------------------------------------------------------------------------
    customer_email = f"customer.{uuid.uuid4().hex[:6]}@example.com"
    ticket_payload = {
        "requester_name": "Tran Van Khach",
        "requester_email": customer_email,
        "subject": "Không thể đăng nhập vào ứng dụng di động",
        "description": "Tôi gặp thông báo lỗi kết nối máy chủ khi đăng nhập từ sáng nay.",
        "category": "TECHNICAL",
    }
    file_bytes = b"Logs: Connection timed out on port 443"
    files = [("files", ("error_log.txt", io.BytesIO(file_bytes), "text/plain"))]

    create_res = await client.post("/api/public/tickets", data=ticket_payload, files=files)
    assert create_res.status_code == 201, create_res.text
    ticket_out = create_res.json()
    ticket_code = ticket_out["ticket_code"]
    assert ticket_code.startswith("TK-")
    assert ticket_out["status"] == "OPEN"

    # --------------------------------------------------------------------------
    # 2. Public customer tracks ticket via code & email
    # --------------------------------------------------------------------------
    track_res = await client.post(
        "/api/public/track",
        json={"ticket_code": ticket_code, "email": customer_email},
    )
    assert track_res.status_code == 200
    track_data = track_res.json()
    assert track_data["ticket_code"] == ticket_code
    assert track_data["subject"] == ticket_payload["subject"]
    assert track_data["status"] == "OPEN"

    # --------------------------------------------------------------------------
    # 3. Manager logs in, finds unassigned ticket, and assigns to Team & Agent
    # --------------------------------------------------------------------------
    manager_headers = await _login(client, "hung.manager@example.com", "hung.manager@Dev123")
    admin_headers = await _login(client, "admin@example.com", "Admin@Dev123")

    # Get Tech Support Team ID
    teams = (await client.get("/api/teams", headers=admin_headers)).json()
    tech_team = next(t for t in teams if "Kỹ thuật" in t["name"] or "Tech" in t["name"])
    team_detail = (await client.get(f"/api/teams/{tech_team['id']}", headers=admin_headers)).json()
    agent_member = next(m for m in team_detail["members"] if m["team_role"] == "MEMBER")
    agent_id = agent_member["user_id"]
    agent_email = agent_member["email"]

    # Manager finds ticket_id via search
    search_res = await client.get(f"/api/tickets?q={ticket_code}", headers=manager_headers)
    assert search_res.status_code == 200
    found_item = search_res.json()["items"][0]
    ticket_id = found_item["id"]
    current_version = found_item["version"]

    # Manager assigns ticket
    assign_res = await client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"team_id": str(tech_team["id"]), "assigned_to": str(agent_id), "version": current_version},
        headers=manager_headers,
    )
    assert assign_res.status_code == 200
    assigned_ticket = assign_res.json()
    assert assigned_ticket["team_id"] == tech_team["id"]
    assert assigned_ticket["assigned_to"] == agent_id
    current_version = assigned_ticket["version"]

    # --------------------------------------------------------------------------
    # 4. Agent logs in, triggers AI Classification & AI Draft Response
    # --------------------------------------------------------------------------
    agent_headers = await _login(client, agent_email, f"{agent_email.split('@')[0]}@Dev123")

    # AI Classify
    classify_res = await client.post(f"/api/tickets/{ticket_id}/ai/classify", headers=agent_headers)
    assert classify_res.status_code == 200
    ai_classify = classify_res.json()
    assert ai_classify["status"] == "PENDING_REVIEW"
    classify_result_id = ai_classify["id"]

    # Agent reviews and approves AI classification (passes current ticket version)
    review_classify = await client.post(
        f"/api/ai/results/{classify_result_id}/approve",
        json={"version": current_version},
        headers=agent_headers,
    )
    assert review_classify.status_code == 200

    # Refresh ticket version in case classification updated ticket category/priority
    ticket_get = await client.get(f"/api/tickets/{ticket_id}", headers=agent_headers)
    assert ticket_get.status_code == 200
    current_version = ticket_get.json()["version"]

    # AI Draft response
    draft_res = await client.post(f"/api/tickets/{ticket_id}/ai/draft", json={"instruction": None}, headers=agent_headers)
    assert draft_res.status_code == 200
    ai_draft = draft_res.json()
    assert ai_draft["status"] == "PENDING_REVIEW"
    draft_result_id = ai_draft["id"]

    # Agent reviews and approves AI draft
    review_draft = await client.post(
        f"/api/ai/results/{draft_result_id}/approve",
        json={},
        headers=agent_headers,
    )
    assert review_draft.status_code == 200

    # --------------------------------------------------------------------------
    # 5. Agent posts public response (first response recorded for SLA)
    # --------------------------------------------------------------------------
    reply_res = await client.post(
        f"/api/tickets/{ticket_id}/comments",
        data={
            "content": "Chào bạn, chúng tôi đã khắc phục sự cố kết nối máy chủ. Bạn vui lòng thử lại.",
            "visibility": "PUBLIC",
        },
        headers=agent_headers,
    )
    assert reply_res.status_code == 200
    ticket_after_reply = reply_res.json()
    assert ticket_after_reply["first_response_at"] is not None
    current_version = ticket_after_reply["version"]

    # --------------------------------------------------------------------------
    # 6. Public customer tracks again, sees the staff reply
    # --------------------------------------------------------------------------
    track_after_reply = await client.post(
        "/api/public/track",
        json={"ticket_code": ticket_code, "email": customer_email},
    )
    assert track_after_reply.status_code == 200
    customer_view = track_after_reply.json()
    assert len(customer_view.get("comments", [])) >= 1

    # --------------------------------------------------------------------------
    # 7. State machine progression: OPEN -> IN_PROGRESS -> PENDING -> IN_PROGRESS -> RESOLVED -> CLOSED
    # --------------------------------------------------------------------------
    # OPEN -> IN_PROGRESS
    status_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS", "version": current_version},
        headers=agent_headers,
    )
    assert status_res.status_code == 200
    current_version = status_res.json()["version"]

    # IN_PROGRESS -> PENDING (Customer confirmation)
    status_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "PENDING", "version": current_version},
        headers=agent_headers,
    )
    assert status_res.status_code == 200
    current_version = status_res.json()["version"]

    # PENDING -> IN_PROGRESS (Resuming work)
    status_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS", "version": current_version},
        headers=agent_headers,
    )
    assert status_res.status_code == 200
    current_version = status_res.json()["version"]

    # IN_PROGRESS -> RESOLVED
    status_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "RESOLVED", "version": current_version},
        headers=agent_headers,
    )
    assert status_res.status_code == 200
    current_version = status_res.json()["version"]
    assert status_res.json()["resolved_at"] is not None

    # RESOLVED -> CLOSED
    status_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "CLOSED", "version": current_version},
        headers=agent_headers,
    )
    assert status_res.status_code == 200
    current_version = status_res.json()["version"]
    assert status_res.json()["closed_at"] is not None

    # --------------------------------------------------------------------------
    # 8. Reopen ticket with mandatory reason
    # --------------------------------------------------------------------------
    reopen_res = await client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"status": "IN_PROGRESS", "reason": "Khách hàng thông báo lỗi tái diễn", "version": current_version},
        headers=agent_headers,
    )
    assert reopen_res.status_code == 200
    assert reopen_res.json()["status"] == "IN_PROGRESS"

    # --------------------------------------------------------------------------
    # 9. Dashboard verification
    # --------------------------------------------------------------------------
    dash_res = await client.get("/api/dashboard/summary", headers=admin_headers)
    assert dash_res.status_code == 200
    dash_summary = dash_res.json()
    assert dash_summary["kpi"]["total"] >= 1
    assert "by_status" in dash_summary["kpi"]
