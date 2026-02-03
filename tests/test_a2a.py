"""
A2A Protocol compliance tests.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_a2a_agent_card_structure(client: AsyncClient):
    """Test that agent card has required A2A fields."""
    response = await client.get("/.well-known/agent.json")

    assert response.status_code == 200
    card = response.json()

    # Required A2A fields
    assert "name" in card
    assert "description" in card
    assert "version" in card
    assert "protocol" in card
    assert "capabilities" in card

    # Check protocol version format
    assert card["protocol"].startswith("a2a/")


@pytest.mark.asyncio
async def test_a2a_task_send(client: AsyncClient):
    """Test A2A task/send endpoint."""
    response = await client.post(
        "/a2a/tasks/send",
        json={
            "id": "test-request-1",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Hello, Agent Polis!"}],
                },
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    # JSON-RPC response structure
    assert data["id"] == "test-request-1"
    assert "result" in data or "error" in data

    if "result" in data:
        result = data["result"]
        assert "task" in result
        assert "id" in result["task"]
        assert "status" in result["task"]


@pytest.mark.asyncio
async def test_a2a_task_status(client: AsyncClient):
    """Test getting A2A task status."""
    # First create a task
    create_response = await client.post(
        "/a2a/tasks/send",
        json={
            "id": "test-create",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Test message"}],
                },
            },
        },
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["result"]["task"]["id"]

    # Get task status
    status_response = await client.get(f"/a2a/tasks/{task_id}")

    assert status_response.status_code == 200
    task = status_response.json()
    assert task["id"] == task_id
    assert "status" in task
    assert "messages" in task


@pytest.mark.asyncio
async def test_a2a_task_not_found(client: AsyncClient):
    """Test 404 for non-existent task."""
    response = await client.get("/a2a/tasks/nonexistent-task-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a2a_help_response(client: AsyncClient):
    """Test that agent responds to help requests."""
    response = await client.post(
        "/a2a/tasks/send",
        json={
            "id": "help-request",
            "method": "tasks/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "help"}],
                },
            },
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]

    # Check that response mentions capabilities
    message = result["message"]
    assert message["role"] == "agent"

    text_parts = [p["text"] for p in message["parts"] if p.get("kind") == "text"]
    full_text = " ".join(text_parts).lower()

    assert "simulation" in full_text or "governance" in full_text
