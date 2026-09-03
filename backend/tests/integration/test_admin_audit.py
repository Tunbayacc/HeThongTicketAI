import os
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
    return resp.json()["access_token"]


async def test_audit_logs_read_and_filter(client: httpx.AsyncClient):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/audit-logs", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    # Test filtering by entity_type
    res_filter = await client.get("/api/audit-logs?entity_type=USER", headers=headers)
    assert res_filter.status_code == 200
    for item in res_filter.json()["items"]:
        assert item["entity_type"] == "USER"

    # Non-admin access rejected
    agent_resp = await client.post("/api/auth/login", json={"email": "lan.agent@example.com", "password": "lan.agent@Dev123"})
    agent_token = agent_resp.json()["access_token"]
    res_denied = await client.get("/api/audit-logs", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_denied.status_code == 403
