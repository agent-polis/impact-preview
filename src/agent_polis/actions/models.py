"""
Pydantic models for the action/impact preview system.

These models define the core data structures for:
- Proposed actions (what an agent wants to do)
- Impact previews (what will change if approved)
- Approval workflow states
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions that can be intercepted and previewed."""
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_MOVE = "file_move"
    FILE_CREATE = "file_create"
    DB_QUERY = "db_query"
    DB_EXECUTE = "db_execute"
    API_CALL = "api_call"
    SHELL_COMMAND = "shell_command"
    CUSTOM = "custom"


class ApprovalStatus(str, Enum):
    """Status of an action in the approval workflow."""
    PENDING = "pending"         # Awaiting human review
    APPROVED = "approved"       # Human approved
    REJECTED = "rejected"       # Human rejected
    MODIFIED = "modified"       # Human modified then approved
    EXECUTED = "executed"       # Action was executed
    FAILED = "failed"           # Execution failed
    TIMED_OUT = "timed_out"     # No response within timeout
    CANCELLED = "cancelled"     # Agent cancelled the request


class RiskLevel(str, Enum):
    """Risk assessment for a proposed action."""
    LOW = "low"           # Read operations, safe changes
    MEDIUM = "medium"     # Write operations to non-critical files
    HIGH = "high"         # Delete, system files, production data
    CRITICAL = "critical" # Irreversible, production database, etc.


class FileChange(BaseModel):
    """Represents a change to a single file."""
    
    path: str = Field(description="File path (relative or absolute)")
    operation: str = Field(description="Operation type: create, modify, delete, move")
    
    # For modifications
    original_content: str | None = Field(
        default=None,
        description="Original file content (for modifications)",
    )
    new_content: str | None = Field(
        default=None,
        description="New file content (for create/modify)",
    )
    
    # For moves
    destination_path: str | None = Field(
        default=None,
        description="Destination path (for move operations)",
    )
    
    # Diff
    diff: str | None = Field(
        default=None,
        description="Unified diff format showing changes",
    )
    
    # Metadata
    lines_added: int = Field(default=0)
    lines_removed: int = Field(default=0)
    file_size_before: int | None = Field(default=None)
    file_size_after: int | None = Field(default=None)


class ActionRequest(BaseModel):
    """
    A proposed action submitted by an AI agent.
    
    This is what agents send when they want to do something
    that requires human approval.
    """
    
    action_type: ActionType = Field(
        description="Type of action being proposed",
    )
    
    description: str = Field(
        max_length=500,
        description="Human-readable description of what the action does",
    )
    
    # Action-specific details
    target: str = Field(
        description="Target of the action (file path, DB table, API endpoint, etc.)",
    )
    
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific data (content, query, request body, etc.)",
    )
    
    # Context
    context: str | None = Field(
        default=None,
        max_length=2000,
        description="Why the agent wants to do this (reasoning/context)",
    )
    
    # Options
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="How long to wait for approval before timing out",
    )
    
    auto_approve_if_low_risk: bool = Field(
        default=False,
        description="Automatically approve if assessed as low risk",
    )
    
    callback_url: str | None = Field(
        default=None,
        max_length=500,
        description="Webhook URL to call when action is approved/rejected",
    )


class ActionPreview(BaseModel):
    """
    Impact preview showing what will change if the action is approved.
    
    This is the core value proposition - show the diff BEFORE execution.
    """
    
    # What will change
    file_changes: list[FileChange] = Field(
        default_factory=list,
        description="List of file changes that will occur",
    )
    
    # Risk assessment
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM,
        description="Assessed risk level of this action",
    )
    
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Specific risk factors identified",
    )
    
    # Summary
    summary: str = Field(
        description="Human-readable summary of the impact",
    )
    
    affected_count: int = Field(
        default=0,
        description="Number of items affected (files, rows, etc.)",
    )
    
    # Warnings
    warnings: list[str] = Field(
        default_factory=list,
        description="Warning messages about potential issues",
    )
    
    # Reversibility
    is_reversible: bool = Field(
        default=True,
        description="Whether this action can be undone",
    )
    
    reversal_instructions: str | None = Field(
        default=None,
        description="How to reverse this action if needed",
    )


class ActionResponse(BaseModel):
    """Response model for action operations."""
    
    id: UUID = Field(default_factory=uuid4)
    
    # Request details
    action_type: ActionType
    description: str
    target: str
    
    # Status
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    
    # Preview (generated after submission)
    preview: ActionPreview | None = Field(default=None)
    
    # Approval details
    approved_by: UUID | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    rejection_reason: str | None = Field(default=None)
    
    # Execution details
    executed_at: datetime | None = Field(default=None)
    execution_result: dict[str, Any] | None = Field(default=None)
    execution_error: str | None = Field(default=None)
    
    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = Field(default=None)
    
    # Agent info
    agent_id: UUID | None = Field(default=None)
    agent_name: str | None = Field(default=None)
    
    class Config:
        from_attributes = True


class ActionListResponse(BaseModel):
    """Response for listing actions."""
    
    actions: list[ActionResponse]
    total: int
    pending_count: int
    page: int
    page_size: int


class ApprovalRequest(BaseModel):
    """Request to approve an action."""
    
    comment: str | None = Field(
        default=None,
        max_length=500,
        description="Optional comment explaining approval",
    )


class RejectionRequest(BaseModel):
    """Request to reject an action."""
    
    reason: str = Field(
        max_length=500,
        description="Reason for rejection",
    )


class ModificationRequest(BaseModel):
    """Request to modify an action before approval."""
    
    modified_payload: dict[str, Any] = Field(
        description="Modified action payload",
    )
    
    comment: str | None = Field(
        default=None,
        max_length=500,
        description="Explanation of modifications",
    )
