import pytest
from httpx import AsyncClient

from a10_guardian.main import app


@pytest.mark.asyncio
async def test_health_check():
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "up"}
