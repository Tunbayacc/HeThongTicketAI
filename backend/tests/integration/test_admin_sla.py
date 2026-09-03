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


async def _token(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Admin@Dev123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def test_sla_policy_crud_and_conflict(client: httpx.AsyncClient):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List existing policies
    res = await client.get("/api/sla-policies", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 4

    # 2. Create policy with overlapping effective period -> 409 SLA_POLICY_CONFLICT
    overlap_payload = {
        "name": "Overlapping URGENT",
        "priority": "URGENT",
        "first_response_minutes": 10,
        "resolution_minutes": 120,
        "pause_on_pending": False,
        "effective_from": "2025-01-01T00:00:00Z",
        "effective_to": None,
        "is_active": True,
    }
    res_conflict = await client.post("/api/sla-policies", json=overlap_payload, headers=headers)
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error_code"] == "SLA_POLICY_CONFLICT"

    # 3. Cap existing LOW policy's effective_to so it doesn't extend to infinity
    low_pol = next(p for p in res.json() if p["priority"] == "LOW" and p["is_active"])
    await client.patch(
        f"/api/sla-policies/{low_pol['id']}",
        json={"effective_to": "2030-01-01T00:00:00Z"},
        headers=headers,
    )

    # 4. Create non-overlapping future policy -> 201
    valid_payload = {
        "name": "Future Policy",
        "priority": "LOW",
        "first_response_minutes": 200,
        "resolution_minutes": 1000,
        "pause_on_pending": True,
        "effective_from": "2030-01-01T00:00:00Z",
        "effective_to": "2031-01-01T00:00:00Z",
        "is_active": True,
    }
    res_created = await client.post("/api/sla-policies", json=valid_payload, headers=headers)
    assert res_created.status_code == 201
    pol_id = res_created.json()["id"]

    # 4. Update policy
    res_updated = await client.patch(
        f"/api/sla-policies/{pol_id}",
        json={"name": "Future Policy Renamed", "first_response_minutes": 250},
        headers=headers,
    )
    assert res_updated.status_code == 200
    assert res_updated.json()["name"] == "Future Policy Renamed"
    assert res_updated.json()["first_response_minutes"] == 250
