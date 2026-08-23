"""
Smoke test proving the test harness itself works: the real FastAPI app
boots over ASGITransport with the DB/Redis test doubles from conftest.py
wired in, with no real Postgres/Redis required.
"""


async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
