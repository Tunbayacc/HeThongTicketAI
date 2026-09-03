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


async def test_s6_demo_scenario(client: httpx.AsyncClient):
    """Demo: admin tạo user mới -> gán team -> đăng nhập user đó (master spec §10 S6)."""
    # 1. Admin login
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Admin@Dev123"},
    )
    assert login_res.status_code == 200
    admin_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin creates user
    unique_email = f"agent.demo.{uuid.uuid4().hex[:6]}@example.com"
    user_res = await client.post(
        "/api/users",
        json={
            "full_name": "Demo Support Agent",
            "email": unique_email,
            "password": "DemoPassword123!",
            "role": "AGENT",
        },
        headers=headers,
    )
    assert user_res.status_code == 201
    new_user = user_res.json()

    # 3. Admin gets a team and adds user
    teams_res = await client.get("/api/teams", headers=headers)
    assert teams_res.status_code == 200
    team_id = teams_res.json()[0]["id"]

    add_res = await client.post(
        f"/api/teams/{team_id}/members",
        json={"user_id": new_user["id"], "team_role": "MEMBER"},
        headers=headers,
    )
    assert add_res.status_code == 200

    # Verify team detail reflects the new member
    detail_res = await client.get(f"/api/teams/{team_id}", headers=headers)
    assert detail_res.status_code == 200
    assert any(m["user_id"] == new_user["id"] for m in detail_res.json()["members"])

    # 4. New user logs in successfully
    new_login = await client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "DemoPassword123!"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["user"]["email"] == unique_email
    assert new_login.json()["user"]["role"] == "AGENT"
