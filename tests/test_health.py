"""
Basic health check tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_agent_card(client: AsyncClient):
    """Test the A2A agent card endpoint."""
    response = await client.get("/.well-known/agent.json")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Agent Polis"
    assert "protocol" in data
    assert data["protocol"] == "a2a/1.0"
    assert "capabilities" in data
    # v0.2 capabilities focus on impact preview
    assert "impact_preview" in data["capabilities"]
    assert "action_approval" in data["capabilities"]
