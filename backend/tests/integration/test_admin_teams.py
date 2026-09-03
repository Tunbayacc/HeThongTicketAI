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


async def _token(client: httpx.AsyncClient, email: str = "admin@example.com") -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": "Admin@Dev123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_team_crud_and_membership(client: httpx.AsyncClient):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create team
    team_payload = {"name": f"Team Test {uuid.uuid4().hex[:6]}", "description": "Test team"}
    res = await client.post("/api/teams", json=team_payload, headers=headers)
    assert res.status_code == 201
    team_id = res.json()["id"]

    # Duplicate name -> 409
    res_dup = await client.post("/api/teams", json=team_payload, headers=headers)
    assert res_dup.status_code == 409

    # 2. Create an active agent & an inactive user
    u_active = (await client.post("/api/users", json={
        "full_name": "Active Agent", "email": f"act.{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!", "role": "AGENT"
    }, headers=headers)).json()

    u_inactive = (await client.post("/api/users", json={
        "full_name": "Inactive Agent", "email": f"inact.{uuid.uuid4().hex[:6]}@example.com",
        "password": "Password123!", "role": "AGENT"
    }, headers=headers)).json()
    await client.patch(f"/api/users/{u_inactive['id']}", json={"is_active": False}, headers=headers)

    # 3. Add active user to team -> 200/201
    res_add = await client.post(
        f"/api/teams/{team_id}/members",
        json={"user_id": u_active["id"], "team_role": "MEMBER"},
        headers=headers,
    )
    assert res_add.status_code in (200, 201)

    # 4. Add inactive user to team -> 400 BAD_REQUEST (FR-ADM-08)
    res_bad = await client.post(
        f"/api/teams/{team_id}/members",
        json={"user_id": u_inactive["id"], "team_role": "MEMBER"},
        headers=headers,
    )
    assert res_bad.status_code == 400
    assert "không hoạt động" in res_bad.json()["message"]

    # 5. List teams includes our created team
    res_list = await client.get("/api/teams", headers=headers)
    assert res_list.status_code == 200
    assert any(t["id"] == team_id for t in res_list.json())

    # 6. Get team detail includes active member
    res_detail = await client.get(f"/api/teams/{team_id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["member_count"] >= 1
    assert any(m["user_id"] == u_active["id"] for m in res_detail.json()["members"])

    # 7. Remove member from team -> 204
    res_del = await client.delete(
        f"/api/teams/{team_id}/members/{u_active['id']}",
        headers=headers,
    )
    assert res_del.status_code == 204

    # Member is now inactive in detail
    res_after = await client.get(f"/api/teams/{team_id}", headers=headers)
    assert res_after.status_code == 200
    member_record = next(m for m in res_after.json()["members"] if m["user_id"] == u_active["id"])
    assert member_record["is_active"] is False
