"""
Agent registration and management tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient):
    """Test agent registration."""
    response = await client.post(
        "/api/v1/agents/register",
        json={
            "name": "test-agent",
            "description": "A test agent",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-agent"
    assert data["description"] == "A test agent"
    assert data["status"] == "active"
    assert "api_key" in data
    assert data["api_key"].startswith("ap_")


@pytest.mark.asyncio
async def test_register_duplicate_name(client: AsyncClient):
    """Test that duplicate agent names are rejected."""
    # First registration
    response1 = await client.post(
        "/api/v1/agents/register",
        json={
            "name": "duplicate-agent",
            "description": "First agent",
        },
    )
    assert response1.status_code == 201

    # Second registration with same name
    response2 = await client.post(
        "/api/v1/agents/register",
        json={
            "name": "duplicate-agent",
            "description": "Second agent",
        },
    )
    assert response2.status_code == 400
    assert "already taken" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_agent_name(client: AsyncClient):
    """Test that invalid agent names are rejected."""
    response = await client.post(
        "/api/v1/agents/register",
        json={
            "name": "invalid name with spaces",
            "description": "Should fail",
        },
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_current_agent(client: AsyncClient, registered_agent: dict, auth_headers: dict):
    """Test getting current agent profile."""
    response = await client.get(
        "/api/v1/agents/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == registered_agent["name"]
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_get_agent_stats(client: AsyncClient, auth_headers: dict):
    """Test getting agent statistics."""
    response = await client.get(
        "/api/v1/agents/me/stats",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_simulations"] == 0
    assert data["simulations_this_month"] == 0
    assert "monthly_limit" in data


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test that unauthenticated requests are rejected."""
    response = await client.get("/api/v1/agents/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key(client: AsyncClient):
    """Test that invalid API keys are rejected."""
    response = await client.get(
        "/api/v1/agents/me",
        headers={"X-API-Key": "invalid_key"},
    )
    assert response.status_code == 401
