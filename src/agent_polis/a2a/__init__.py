"""
A2A Protocol implementation for Agent Polis.

This module implements the Agent-to-Agent (A2A) protocol for agent discovery
and task management. A2A is the emerging standard for agent interoperability.
"""

from agent_polis.a2a.router import router
from agent_polis.a2a.models import TaskRequest, TaskResponse, TaskStatus

__all__ = ["router", "TaskRequest", "TaskResponse", "TaskStatus"]
