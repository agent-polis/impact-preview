"""
Action API routes - the core of impact preview.

These endpoints handle:
- Submitting proposed actions
- Viewing impact previews
- Approving/rejecting actions
- Executing approved actions
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.actions.diff import format_diff_plain, format_diff_terminal
from agent_polis.actions.models import (
    ActionListResponse,
    ActionRequest,
    ActionResponse,
    ApprovalRequest,
    ApprovalStatus,
    RejectionRequest,
)
from agent_polis.actions.service import ActionService
from agent_polis.shared.db import get_db
from agent_polis.shared.security import CurrentAgent

logger = structlog.get_logger()
router = APIRouter()


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def submit_action(
    request: ActionRequest,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionResponse:
    """
    Submit a proposed action for approval.
    
    The action will be analyzed and a preview will be generated showing
    exactly what will change. The action remains pending until approved.
    
    If `auto_approve_if_low_risk` is True and the action is assessed as
    low risk, it will be automatically approved.
    """
    service = ActionService(db)
    
    action, preview = await service.submit(request, agent)
    response = service.to_response(action)
    
    # Attach agent name for response
    response.agent_name = agent.name
    
    return response


@router.get("/", response_model=ActionListResponse)
async def list_actions(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> ActionListResponse:
    """List actions submitted by the current agent."""
    service = ActionService(db)
    
    actions, total = await service.list_by_agent(
        agent_id=agent.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    
    # Get pending count
    _, _, pending_count = await service.list_pending(agent_id=agent.id)
    
    return ActionListResponse(
        actions=[service.to_response(a) for a in actions],
        total=total,
        pending_count=pending_count,
        page=page,
        page_size=page_size,
    )


@router.get("/pending", response_model=ActionListResponse)
async def list_pending_actions(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    all_agents: bool = Query(default=False, description="Show pending actions from all agents"),
) -> ActionListResponse:
    """
    List pending actions awaiting approval.
    
    By default, shows only the current agent's pending actions.
    Set `all_agents=true` to see all pending actions (for reviewers).
    """
    service = ActionService(db)
    
    agent_id = None if all_agents else agent.id
    actions, total, pending_count = await service.list_pending(
        agent_id=agent_id,
        page=page,
        page_size=page_size,
    )
    
    return ActionListResponse(
        actions=[service.to_response(a) for a in actions],
        total=total,
        pending_count=pending_count,
        page=page,
        page_size=page_size,
    )


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionResponse:
    """Get details of a specific action."""
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    return service.to_response(action)


@router.get("/{action_id}/preview")
async def get_action_preview(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Get the impact preview for an action.
    
    Returns the full preview with file changes, risk assessment, and warnings.
    """
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    if not action.preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not yet generated",
        )
    
    return action.preview


@router.get("/{action_id}/diff")
async def get_action_diff(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query(default="plain", description="Output format: plain, terminal, or json"),
) -> dict:
    """
    Get the diff for file changes in an action.
    
    Formats:
    - `plain`: Simple text diff
    - `terminal`: ANSI-colored for terminal display
    - `json`: Structured JSON with all change details
    """
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    if not action.preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not yet generated",
        )
    
    from agent_polis.actions.models import ActionPreview, FileChange
    
    preview = ActionPreview(**action.preview)
    
    if format == "json":
        return {
            "action_id": str(action_id),
            "summary": preview.summary,
            "file_changes": [c.model_dump() for c in preview.file_changes],
        }
    elif format == "terminal":
        return {
            "action_id": str(action_id),
            "diff": format_diff_terminal(preview.file_changes),
        }
    else:
        return {
            "action_id": str(action_id),
            "diff": format_diff_plain(preview.file_changes),
        }


@router.post("/{action_id}/approve", response_model=ActionResponse)
async def approve_action(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: ApprovalRequest | None = None,
) -> ActionResponse:
    """
    Approve a pending action.
    
    Once approved, the action can be executed.
    """
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    try:
        comment = request.comment if request else None
        action = await service.approve(action, agent, comment=comment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return service.to_response(action)


@router.post("/{action_id}/reject", response_model=ActionResponse)
async def reject_action(
    action_id: UUID,
    request: RejectionRequest,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionResponse:
    """
    Reject a pending action.
    
    A reason must be provided to help the agent understand why.
    """
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    try:
        action = await service.reject(action, agent, request.reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return service.to_response(action)


@router.post("/{action_id}/execute", response_model=ActionResponse)
async def execute_action(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionResponse:
    """
    Execute an approved action.
    
    The action must be approved before it can be executed.
    This endpoint marks the action as executed - the actual operation
    is performed by the agent after receiving confirmation.
    """
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    try:
        action = await service.execute(action, agent)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return service.to_response(action)


@router.get("/{action_id}/events")
async def get_action_events(
    action_id: UUID,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    """
    Get the event history for an action.
    
    Returns a complete audit trail of everything that happened
    with this action - useful for compliance and debugging.
    """
    from agent_polis.events.store import EventStore
    
    service = ActionService(db)
    action = await service.get_by_id(action_id)
    
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    
    event_store = EventStore(db)
    events = await event_store.get_stream(f"action:{action_id}")
    
    return [
        {
            "id": str(e.id),
            "type": e.event_type,
            "data": e.event_data,
            "metadata": e.event_metadata,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
