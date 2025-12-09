"""Tests for health endpoint."""

from httpx import AsyncClient

from src import __version__


async def test_health_check(client: AsyncClient) -> None:
    """Test that health endpoint returns healthy status."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == __version__
