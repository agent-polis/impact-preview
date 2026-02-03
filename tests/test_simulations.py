"""
Simulation creation and execution tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_simulation(client: AsyncClient, auth_headers: dict):
    """Test creating a simulation."""
    response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Test Simulation",
                "description": "A test scenario",
                "code": "result = 2 + 2",
                "inputs": {},
                "timeout_seconds": 30,
            }
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["scenario"]["name"] == "Test Simulation"
    assert "id" in data


@pytest.mark.asyncio
async def test_run_simulation(client: AsyncClient, auth_headers: dict):
    """Test running a simulation."""
    # Create simulation
    create_response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Run Test",
                "code": "result = {'value': 42}",
                "inputs": {},
                "timeout_seconds": 30,
            }
        },
    )
    assert create_response.status_code == 201
    sim_id = create_response.json()["id"]

    # Run simulation
    run_response = await client.post(
        f"/api/v1/simulations/{sim_id}/run",
        headers=auth_headers,
    )

    assert run_response.status_code == 200
    result = run_response.json()
    assert result["success"] is True
    assert result["output"] == {"value": 42}


@pytest.mark.asyncio
async def test_simulation_with_inputs(client: AsyncClient, auth_headers: dict):
    """Test simulation with input variables."""
    create_response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Input Test",
                "code": "result = x * 2",
                "inputs": {"x": 21},
                "timeout_seconds": 30,
            }
        },
    )
    assert create_response.status_code == 201
    sim_id = create_response.json()["id"]

    run_response = await client.post(
        f"/api/v1/simulations/{sim_id}/run",
        headers=auth_headers,
    )

    assert run_response.status_code == 200
    result = run_response.json()
    assert result["success"] is True
    assert result["output"] == 42


@pytest.mark.asyncio
async def test_simulation_failure(client: AsyncClient, auth_headers: dict):
    """Test simulation that fails."""
    create_response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Failure Test",
                "code": "raise ValueError('intentional error')",
                "inputs": {},
                "timeout_seconds": 30,
            }
        },
    )
    assert create_response.status_code == 201
    sim_id = create_response.json()["id"]

    run_response = await client.post(
        f"/api/v1/simulations/{sim_id}/run",
        headers=auth_headers,
    )

    assert run_response.status_code == 200
    result = run_response.json()
    assert result["success"] is False
    assert "intentional error" in result["error"]


@pytest.mark.asyncio
async def test_list_simulations(client: AsyncClient, auth_headers: dict):
    """Test listing simulations."""
    # Create a simulation first
    await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "List Test",
                "code": "result = True",
                "inputs": {},
            }
        },
    )

    response = await client.get(
        "/api/v1/simulations",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "simulations" in data
    assert "total" in data
    assert len(data["simulations"]) >= 1


@pytest.mark.asyncio
async def test_get_simulation_events(client: AsyncClient, auth_headers: dict):
    """Test getting simulation event audit trail."""
    # Create and run a simulation
    create_response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Events Test",
                "code": "result = 1",
                "inputs": {},
            }
        },
    )
    sim_id = create_response.json()["id"]

    await client.post(
        f"/api/v1/simulations/{sim_id}/run",
        headers=auth_headers,
    )

    # Get events
    response = await client.get(
        f"/api/v1/simulations/{sim_id}/events",
        headers=auth_headers,
    )

    assert response.status_code == 200
    events = response.json()
    assert len(events) >= 2  # At least SimulationCreated and SimulationCompleted

    event_types = [e["type"] for e in events]
    assert "SimulationCreated" in event_types


@pytest.mark.asyncio
async def test_record_prediction(client: AsyncClient, auth_headers: dict):
    """Test recording outcome predictions."""
    # Create simulation
    create_response = await client.post(
        "/api/v1/simulations",
        headers=auth_headers,
        json={
            "scenario": {
                "name": "Prediction Test",
                "code": "result = True",
                "inputs": {},
            }
        },
    )
    sim_id = create_response.json()["id"]

    # Record prediction
    response = await client.post(
        f"/api/v1/simulations/{sim_id}/predict",
        headers=auth_headers,
        json={
            "predicted_success": True,
            "confidence": 0.9,
            "rationale": "Simple code should work",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "prediction_recorded"
