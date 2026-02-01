"""
Agent Polis SDK - Easy integration for AI agents.

This SDK provides a simple way to integrate impact preview into
your AI agent workflows. Use the @require_approval decorator to
automatically route dangerous operations through the approval flow.

Usage:
    from agent_polis.sdk import AgentPolisClient, require_approval
    
    client = AgentPolisClient(api_key="your_api_key")
    
    @client.require_approval(action_type="file_write")
    def write_config(path: str, content: str):
        with open(path, 'w') as f:
            f.write(content)
    
    # This will now:
    # 1. Submit the action for approval
    # 2. Wait for approval (with timeout)
    # 3. Execute only if approved
    write_config("/etc/myapp/config.yaml", "new config content")
"""

import functools
import time
from typing import Any, Callable, TypeVar
from uuid import UUID

import httpx

from agent_polis.actions.models import ActionRequest, ActionType, ApprovalStatus

F = TypeVar("F", bound=Callable[..., Any])


class ActionRejectedError(Exception):
    """Raised when an action is rejected."""
    
    def __init__(self, action_id: str, reason: str):
        self.action_id = action_id
        self.reason = reason
        super().__init__(f"Action {action_id} was rejected: {reason}")


class ActionTimedOutError(Exception):
    """Raised when an action times out waiting for approval."""
    
    def __init__(self, action_id: str, timeout: int):
        self.action_id = action_id
        self.timeout = timeout
        super().__init__(f"Action {action_id} timed out after {timeout} seconds")


class AgentPolisClient:
    """
    Client for the Agent Polis impact preview API.
    
    Use this client to submit actions for approval and integrate
    impact preview into your agent workflows.
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str = "",
        default_timeout: int = 300,
        poll_interval: int = 2,
    ):
        """
        Initialize the client.
        
        Args:
            api_url: Base URL of the Agent Polis API
            api_key: API key for authentication
            default_timeout: Default timeout for approvals (seconds)
            poll_interval: How often to poll for approval status
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.default_timeout = default_timeout
        self.poll_interval = poll_interval
        self._client = httpx.Client(
            base_url=api_url,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            },
            timeout=30,
        )
    
    def submit_action(
        self,
        action_type: ActionType | str,
        target: str,
        description: str,
        payload: dict | None = None,
        context: str | None = None,
        timeout_seconds: int | None = None,
        auto_approve_if_low_risk: bool = False,
    ) -> dict:
        """
        Submit an action for approval.
        
        Returns the action response with preview.
        """
        if isinstance(action_type, str):
            action_type = ActionType(action_type)
        
        response = self._client.post(
            "/api/v1/actions",
            json={
                "action_type": action_type.value,
                "target": target,
                "description": description,
                "payload": payload or {},
                "context": context,
                "timeout_seconds": timeout_seconds or self.default_timeout,
                "auto_approve_if_low_risk": auto_approve_if_low_risk,
            },
        )
        response.raise_for_status()
        return response.json()
    
    def get_action(self, action_id: str | UUID) -> dict:
        """Get action details."""
        response = self._client.get(f"/api/v1/actions/{action_id}")
        response.raise_for_status()
        return response.json()
    
    def get_preview(self, action_id: str | UUID) -> dict:
        """Get impact preview for an action."""
        response = self._client.get(f"/api/v1/actions/{action_id}/preview")
        response.raise_for_status()
        return response.json()
    
    def get_diff(self, action_id: str | UUID, format: str = "plain") -> dict:
        """Get diff for an action."""
        response = self._client.get(
            f"/api/v1/actions/{action_id}/diff",
            params={"format": format},
        )
        response.raise_for_status()
        return response.json()
    
    def approve(self, action_id: str | UUID, comment: str | None = None) -> dict:
        """Approve an action."""
        body = {"comment": comment} if comment else {}
        response = self._client.post(
            f"/api/v1/actions/{action_id}/approve",
            json=body,
        )
        response.raise_for_status()
        return response.json()
    
    def reject(self, action_id: str | UUID, reason: str) -> dict:
        """Reject an action."""
        response = self._client.post(
            f"/api/v1/actions/{action_id}/reject",
            json={"reason": reason},
        )
        response.raise_for_status()
        return response.json()
    
    def execute(self, action_id: str | UUID) -> dict:
        """Mark an action as executed."""
        response = self._client.post(f"/api/v1/actions/{action_id}/execute")
        response.raise_for_status()
        return response.json()
    
    def list_pending(self, all_agents: bool = False) -> list[dict]:
        """List pending actions."""
        response = self._client.get(
            "/api/v1/actions/pending",
            params={"all_agents": all_agents},
        )
        response.raise_for_status()
        return response.json()["actions"]
    
    def wait_for_approval(
        self,
        action_id: str | UUID,
        timeout: int | None = None,
    ) -> dict:
        """
        Wait for an action to be approved or rejected.
        
        Args:
            action_id: Action to wait for
            timeout: Maximum time to wait (seconds)
            
        Returns:
            Final action state
            
        Raises:
            ActionRejectedError: If the action is rejected
            ActionTimedOutError: If the timeout is reached
        """
        timeout = timeout or self.default_timeout
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise ActionTimedOutError(str(action_id), timeout)
            
            action = self.get_action(action_id)
            status = action["status"]
            
            if status == "approved":
                return action
            elif status == "rejected":
                raise ActionRejectedError(
                    str(action_id),
                    action.get("rejection_reason", "No reason provided"),
                )
            elif status == "timed_out":
                raise ActionTimedOutError(str(action_id), timeout)
            elif status != "pending":
                # Some other terminal state
                return action
            
            time.sleep(self.poll_interval)
    
    def submit_and_wait(
        self,
        action_type: ActionType | str,
        target: str,
        description: str,
        payload: dict | None = None,
        context: str | None = None,
        timeout_seconds: int | None = None,
        auto_approve_if_low_risk: bool = False,
    ) -> dict:
        """
        Submit an action and wait for approval.
        
        Convenience method that combines submit_action and wait_for_approval.
        """
        action = self.submit_action(
            action_type=action_type,
            target=target,
            description=description,
            payload=payload,
            context=context,
            timeout_seconds=timeout_seconds,
            auto_approve_if_low_risk=auto_approve_if_low_risk,
        )
        
        # If already approved (auto-approve), return immediately
        if action["status"] == "approved":
            return action
        
        return self.wait_for_approval(action["id"], timeout_seconds)
    
    def require_approval(
        self,
        action_type: ActionType | str = ActionType.CUSTOM,
        description: str | None = None,
        auto_approve_if_low_risk: bool = False,
        timeout_seconds: int | None = None,
    ) -> Callable[[F], F]:
        """
        Decorator that requires approval before function execution.
        
        Usage:
            @client.require_approval(action_type="file_write")
            def write_file(path: str, content: str):
                with open(path, 'w') as f:
                    f.write(content)
        
        The decorated function will:
        1. Submit the action for approval
        2. Wait for approval (blocking)
        3. Execute the original function if approved
        4. Raise ActionRejectedError if rejected
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Build action details from function call
                func_desc = description or f"Execute {func.__name__}"
                
                # Try to extract target from first positional arg
                target = str(args[0]) if args else func.__name__
                
                # Build payload from kwargs and remaining args
                payload = {
                    "function": func.__name__,
                    "args": [str(a) for a in args],
                    "kwargs": {k: str(v) for k, v in kwargs.items()},
                }
                
                # Submit and wait
                action = self.submit_and_wait(
                    action_type=action_type,
                    target=target,
                    description=func_desc,
                    payload=payload,
                    auto_approve_if_low_risk=auto_approve_if_low_risk,
                    timeout_seconds=timeout_seconds,
                )
                
                # Execute the original function
                result = func(*args, **kwargs)
                
                # Mark as executed
                self.execute(action["id"])
                
                return result
            
            return wrapper  # type: ignore
        
        return decorator
    
    def close(self):
        """Close the client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick setup
def create_client(
    api_url: str = "http://localhost:8000",
    api_key: str = "",
) -> AgentPolisClient:
    """Create an Agent Polis client."""
    return AgentPolisClient(api_url=api_url, api_key=api_key)
