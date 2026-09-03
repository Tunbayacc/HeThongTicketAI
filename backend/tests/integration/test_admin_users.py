import os
import pytest
import httpx
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


async def _token(client: httpx.AsyncClient, email: str = "admin@example.com", password: str = "Admin@Dev123") -> str:
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_admin_users_requires_admin_role(client: httpx.AsyncClient):
    # Unauthenticated -> 401
    res = await client.get("/api/users")
    assert res.status_code == 401

    # Agent -> 403
    agent_token = await _token(client, "lan.agent@example.com", "lan.agent@Dev123")
    res = await client.get("/api/users", headers={"Authorization": f"Bearer {agent_token}"})
    assert res.status_code == 403
    assert res.json()["error_code"] == "ACCESS_DENIED"


async def test_admin_crud_user_lifecycle(client: httpx.AsyncClient):
    admin_token = await _token(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create user
    new_user = {
        "full_name": "Nguyễn Văn Test",
        "email": "nguyen.test@example.com",
        "password": "Password123!",
        "role": "AGENT",
    }
    res = await client.post("/api/users", json=new_user, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["email"] == "nguyen.test@example.com"
    assert data["role"] == "AGENT"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data
    user_id = data["id"]

    # 2. Duplicate email -> 409
    res_dup = await client.post("/api/users", json=new_user, headers=headers)
    assert res_dup.status_code == 409
    assert res_dup.json()["error_code"] == "CONFLICT"

    # 3. Get user detail
    res_get = await client.get(f"/api/users/{user_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == user_id

    # 4. List users
    res_list = await client.get("/api/users?q=nguyen.test", headers=headers)
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1
    assert any(u["id"] == user_id for u in res_list.json()["items"])

    # 5. Update user
    res_update = await client.patch(
        f"/api/users/{user_id}",
        json={"full_name": "Nguyễn Văn Test (Updated)", "role": "MANAGER"},
        headers=headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["full_name"] == "Nguyễn Văn Test (Updated)"
    assert res_update.json()["role"] == "MANAGER"

    # 6. Deactivate user
    res_deact = await client.patch(
        f"/api/users/{user_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert res_deact.status_code == 200
    assert res_deact.json()["is_active"] is False


async def test_cannot_deactivate_last_admin(client: httpx.AsyncClient):
    admin_token = await _token(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Find the admin user id
    res_me = await client.get("/api/auth/me", headers=headers)
    admin_id = res_me.json()["user"]["id"]

    # Attempt to deactivate admin
    res = await client.patch(
        f"/api/users/{admin_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert res.status_code in (400, 409)
    assert "quản trị viên cuối cùng" in res.json()["message"]
