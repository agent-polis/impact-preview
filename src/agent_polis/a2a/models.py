"""
A2A Protocol Pydantic models.

These models follow the A2A protocol specification for task management
and agent communication.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """A2A task status values."""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


class MessagePart(BaseModel):
    """A part of a message (text, file, etc.)."""
    kind: str = Field(description="Part type (text, file, data)")
    text: str | None = Field(default=None, description="Text content if kind=text")
    data: dict[str, Any] | None = Field(default=None, description="Data content if kind=data")
    mime_type: str | None = Field(default=None, description="MIME type for files")


class Message(BaseModel):
    """A2A message structure."""
    role: str = Field(description="Message role (user, agent)")
    parts: list[MessagePart] = Field(default_factory=list, description="Message parts")
    message_id: str = Field(default_factory=lambda: uuid4().hex, description="Unique message ID")


class TaskRequest(BaseModel):
    """Request to send a task/message to an agent."""
    id: str = Field(default_factory=lambda: uuid4().hex, description="JSON-RPC request ID")
    method: str = Field(default="tasks/send", description="JSON-RPC method")
    params: dict[str, Any] = Field(description="Request parameters")


class TaskSendParams(BaseModel):
    """Parameters for tasks/send method."""
    message: Message = Field(description="Message to send")
    task_id: str | None = Field(default=None, description="Existing task ID to continue")


class TaskResponse(BaseModel):
    """Response from a task operation."""
    id: str = Field(description="JSON-RPC request ID")
    result: dict[str, Any] | None = Field(default=None, description="Success result")
    error: dict[str, Any] | None = Field(default=None, description="Error details")


class Task(BaseModel):
    """A2A Task representation."""
    id: str = Field(default_factory=lambda: uuid4().hex, description="Task ID")
    status: TaskStatus = Field(default=TaskStatus.SUBMITTED, description="Task status")
    messages: list[Message] = Field(default_factory=list, description="Conversation history")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: dict[str, Any] | None = Field(default=None, description="Task result if completed")
    error: str | None = Field(default=None, description="Error message if failed")


class AgentCard(BaseModel):
    """
    A2A Agent Card - describes this agent's capabilities.
    
    This is returned by /.well-known/agent.json for agent discovery.
    """
    name: str = Field(description="Agent name")
    description: str = Field(description="Agent description")
    version: str = Field(description="Agent version")
    protocol: str = Field(default="a2a/1.0", description="Protocol version")
    capabilities: list[str] = Field(default_factory=list, description="Agent capabilities")
    endpoints: dict[str, str] = Field(default_factory=dict, description="API endpoints")
    contact: dict[str, str] | None = Field(default=None, description="Contact information")


# JSON-RPC Error codes (per A2A spec)
class A2AErrorCode:
    """A2A JSON-RPC error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TASK_NOT_FOUND = -32001
    TASK_CANCELED = -32002
    RATE_LIMITED = -32003
