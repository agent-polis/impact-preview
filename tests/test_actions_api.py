"""
Tests for the actions API endpoints.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.fixture
def action_payload():
    """Sample action payload."""
    return {
        "action_type": "file_write",
        "target": "/test/file.txt",
        "description": "Test file write",
        "payload": {"content": "test content"},
    }


@pytest.mark.asyncio
class TestActionsAPI:
    """Tests for actions API."""

    async def test_submit_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test submitting an action."""
        response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["action_type"] == "file_write"
        assert data["status"] == "pending"
        assert data["preview"] is not None

    async def test_submit_action_without_auth(
        self,
        async_client: AsyncClient,
        action_payload: dict,
    ):
        """Test that submitting without auth fails."""
        response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
        )

        assert response.status_code == 401

    async def test_list_actions(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test listing actions."""
        # Create an action first
        await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )

        # List actions
        response = await async_client.get(
            "/api/v1/actions",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert "total" in data
        assert "pending_count" in data

    async def test_list_pending_actions(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test listing pending actions."""
        # Create an action
        await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )

        # List pending
        response = await async_client.get(
            "/api/v1/actions/pending",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pending_count"] >= 1

    async def test_get_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test getting action details."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Get action
        response = await async_client.get(
            f"/api/v1/actions/{action_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == action_id

    async def test_get_action_preview(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test getting action preview."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Get preview
        response = await async_client.get(
            f"/api/v1/actions/{action_id}/preview",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "risk_level" in data
        assert "file_changes" in data

    async def test_get_action_diff(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test getting action diff."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Get diff (plain format)
        response = await async_client.get(
            f"/api/v1/actions/{action_id}/diff?format=plain",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "diff" in data

    async def test_approve_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test approving an action."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Approve
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/approve",
            json={"comment": "Looks good"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approved_at"] is not None

    async def test_reject_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test rejecting an action."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Reject
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/reject",
            json={"reason": "Too risky"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["rejection_reason"] == "Too risky"

    async def test_reject_requires_reason(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test that rejection requires a reason."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Try to reject without reason
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/reject",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_execute_approved_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test executing an approved action."""
        # Create and approve
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        await async_client.post(
            f"/api/v1/actions/{action_id}/approve",
            json={},
            headers=auth_headers,
        )

        # Execute
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/execute",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "executed"
        assert data["executed_at"] is not None

    async def test_cannot_execute_pending_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test that pending actions cannot be executed."""
        # Create (but don't approve)
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Try to execute
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/execute",
            headers=auth_headers,
        )

        assert response.status_code == 400

    async def test_cannot_approve_rejected_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test that rejected actions cannot be approved."""
        # Create and reject
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        await async_client.post(
            f"/api/v1/actions/{action_id}/reject",
            json={"reason": "No"},
            headers=auth_headers,
        )

        # Try to approve
        response = await async_client.post(
            f"/api/v1/actions/{action_id}/approve",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 400

    async def test_get_action_events(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        action_payload: dict,
    ):
        """Test getting action audit trail."""
        # Create an action
        create_response = await async_client.post(
            "/api/v1/actions",
            json=action_payload,
            headers=auth_headers,
        )
        action_id = create_response.json()["id"]

        # Get events
        response = await async_client.get(
            f"/api/v1/actions/{action_id}/events",
            headers=auth_headers,
        )

        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)
        # Should have at least ActionProposed and ActionPreviewGenerated events
        event_types = [e["type"] for e in events]
        assert "ActionProposed" in event_types

    async def test_auto_approve_low_risk(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test auto-approval for low-risk actions."""
        # Safe action with auto-approve enabled
        payload = {
            "action_type": "file_write",
            "target": "/tmp/safe_file.txt",
            "description": "Write to temp file",
            "payload": {"content": "safe content"},
            "auto_approve_if_low_risk": True,
        }

        response = await async_client.post(
            "/api/v1/actions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        # Low-risk actions should be auto-approved
        assert data["status"] in ["pending", "approved"]


@pytest.mark.asyncio
class TestActionsAPIEdgeCases:
    """Edge case tests for actions API."""

    async def test_get_nonexistent_action(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting a non-existent action."""
        fake_id = str(uuid4())
        response = await async_client.get(
            f"/api/v1/actions/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_invalid_action_type(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test submitting with invalid action type."""
        payload = {
            "action_type": "invalid_type",
            "target": "/test",
            "description": "Test",
        }

        response = await async_client.post(
            "/api/v1/actions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_action_with_long_description(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test action with description at max length."""
        payload = {
            "action_type": "file_write",
            "target": "/test",
            "description": "x" * 500,  # Max length
            "payload": {},
        }

        response = await async_client.post(
            "/api/v1/actions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201

    async def test_action_with_callback_url(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        """Test action with callback URL."""
        payload = {
            "action_type": "file_write",
            "target": "/test",
            "description": "Test with callback",
            "payload": {},
            "callback_url": "https://example.com/webhook",
        }

        response = await async_client.post(
            "/api/v1/actions",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
