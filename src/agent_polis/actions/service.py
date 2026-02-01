"""
Action service - business logic for the approval workflow.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.actions.analyzer import ImpactAnalyzer, get_analyzer
from agent_polis.actions.db_models import Action
from agent_polis.actions.models import (
    ActionPreview,
    ActionRequest,
    ActionResponse,
    ActionType,
    ApprovalStatus,
    RiskLevel,
)
from agent_polis.agents.db_models import Agent
from agent_polis.events.bus import publish_event
from agent_polis.events.store import EventStore
from agent_polis.events.types import (
    ActionApproved,
    ActionExecuted,
    ActionFailed,
    ActionMetered,
    ActionProposed,
    ActionPreviewGenerated,
    ActionRejected,
    ActionTimedOut,
)

logger = structlog.get_logger()


class ActionService:
    """Service for managing the action approval workflow."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_store = EventStore(session)
        self.analyzer = get_analyzer()
    
    async def submit(
        self,
        request: ActionRequest,
        agent: Agent,
    ) -> tuple[Action, ActionPreview]:
        """
        Submit a proposed action for approval.
        
        Returns the action record and its preview.
        """
        # Calculate expiry
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.timeout_seconds)
        
        # Create action record
        action = Action(
            agent_id=agent.id,
            action_type=request.action_type.value,
            description=request.description,
            target=request.target,
            payload=request.payload,
            context=request.context,
            status="pending",
            timeout_seconds=request.timeout_seconds,
            auto_approve_if_low_risk=request.auto_approve_if_low_risk,
            callback_url=request.callback_url,
            expires_at=expires_at,
        )
        
        self.session.add(action)
        await self.session.flush()
        
        # Generate preview
        preview = await self.analyzer.analyze(request)
        
        # Store preview in action record
        action.preview = preview.model_dump()
        action.risk_level = preview.risk_level.value
        
        # Record events
        await self._emit_proposed_event(action, agent)
        await self._emit_preview_event(action, preview)
        
        # Auto-approve if low risk and enabled
        if request.auto_approve_if_low_risk and preview.risk_level == RiskLevel.LOW:
            logger.info(
                "Auto-approving low-risk action",
                action_id=str(action.id),
            )
            action.status = "approved"
            action.approved_at = datetime.now(timezone.utc)
            await self._emit_approved_event(action, agent, auto=True)
        
        logger.info(
            "Action submitted",
            action_id=str(action.id),
            action_type=request.action_type,
            risk_level=preview.risk_level,
            status=action.status,
        )
        
        return action, preview
    
    async def approve(
        self,
        action: Action,
        approver: Agent,
        comment: str | None = None,
    ) -> Action:
        """Approve an action for execution."""
        if not action.can_be_approved():
            raise ValueError(f"Action cannot be approved (status: {action.status})")
        
        action.status = "approved"
        action.approved_by = approver.id
        action.approved_at = datetime.now(timezone.utc)
        
        await self._emit_approved_event(action, approver, comment=comment)
        
        # Send callback if configured
        if action.callback_url:
            await self._send_callback(action, "approved")
        
        logger.info(
            "Action approved",
            action_id=str(action.id),
            approver=approver.name,
        )
        
        return action
    
    async def reject(
        self,
        action: Action,
        rejector: Agent,
        reason: str,
    ) -> Action:
        """Reject a proposed action."""
        if action.status != "pending":
            raise ValueError(f"Action cannot be rejected (status: {action.status})")
        
        action.status = "rejected"
        action.rejection_reason = reason
        
        await self._emit_rejected_event(action, rejector, reason)
        
        # Send callback if configured
        if action.callback_url:
            await self._send_callback(action, "rejected")
        
        logger.info(
            "Action rejected",
            action_id=str(action.id),
            rejector=rejector.name,
            reason=reason,
        )
        
        return action
    
    async def execute(
        self,
        action: Action,
        executor: Agent,
    ) -> Action:
        """
        Execute an approved action.
        
        For v0.2, this marks the action as executed but doesn't
        actually perform the operation (that's the agent's job).
        Future versions may execute in sandbox.
        """
        if action.status != "approved":
            raise ValueError(f"Action must be approved before execution (status: {action.status})")
        
        try:
            action.status = "executed"
            action.executed_at = datetime.now(timezone.utc)
            action.execution_result = {"executed_by": str(executor.id)}
            
            await self._emit_executed_event(action, executor)
            
            # Meter the action
            await self._emit_metered_event(action)
            
            # Send callback
            if action.callback_url:
                await self._send_callback(action, "executed")
            
            logger.info(
                "Action executed",
                action_id=str(action.id),
                executor=executor.name,
            )
            
        except Exception as e:
            action.status = "failed"
            action.execution_error = str(e)
            
            await self._emit_failed_event(action, str(e))
            
            if action.callback_url:
                await self._send_callback(action, "failed")
            
            logger.error(
                "Action execution failed",
                action_id=str(action.id),
                error=str(e),
            )
            raise
        
        return action
    
    async def timeout_expired(self, action: Action) -> Action:
        """Mark an action as timed out."""
        if action.status != "pending":
            return action
        
        action.status = "timed_out"
        
        event = ActionTimedOut(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "timeout_seconds": action.timeout_seconds,
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
        
        if action.callback_url:
            await self._send_callback(action, "timed_out")
        
        logger.info("Action timed out", action_id=str(action.id))
        
        return action
    
    async def get_by_id(self, action_id: UUID) -> Action | None:
        """Get an action by ID."""
        result = await self.session.execute(
            select(Action).where(Action.id == action_id)
        )
        return result.scalar_one_or_none()
    
    async def list_pending(
        self,
        agent_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Action], int, int]:
        """
        List pending actions awaiting approval.
        
        Returns (actions, total, pending_count)
        """
        query = select(Action).where(Action.status == "pending")
        count_query = select(func.count(Action.id)).where(Action.status == "pending")
        
        if agent_id:
            query = query.where(Action.agent_id == agent_id)
            count_query = count_query.where(Action.agent_id == agent_id)
        
        # Get pending count
        pending_result = await self.session.execute(count_query)
        pending_count = pending_result.scalar() or 0
        
        # Get total (all statuses for this agent if specified)
        total_query = select(func.count(Action.id))
        if agent_id:
            total_query = total_query.where(Action.agent_id == agent_id)
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0
        
        # Get page
        query = (
            query
            .order_by(Action.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        
        result = await self.session.execute(query)
        actions = list(result.scalars().all())
        
        return actions, total, pending_count
    
    async def list_by_agent(
        self,
        agent_id: UUID,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Action], int]:
        """List actions by agent."""
        query = select(Action).where(Action.agent_id == agent_id)
        count_query = select(func.count(Action.id)).where(Action.agent_id == agent_id)
        
        if status:
            query = query.where(Action.status == status)
            count_query = count_query.where(Action.status == status)
        
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        query = (
            query
            .order_by(Action.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        
        result = await self.session.execute(query)
        actions = list(result.scalars().all())
        
        return actions, total
    
    def to_response(self, action: Action) -> ActionResponse:
        """Convert Action to ActionResponse."""
        preview = None
        if action.preview:
            preview = ActionPreview(**action.preview)
        
        return ActionResponse(
            id=action.id,
            action_type=ActionType(action.action_type),
            description=action.description,
            target=action.target,
            status=ApprovalStatus(action.status),
            preview=preview,
            approved_by=action.approved_by,
            approved_at=action.approved_at,
            rejection_reason=action.rejection_reason,
            executed_at=action.executed_at,
            execution_result=action.execution_result,
            execution_error=action.execution_error,
            created_at=action.created_at,
            expires_at=action.expires_at,
            agent_id=action.agent_id,
        )
    
    # Event emission helpers
    async def _emit_proposed_event(self, action: Action, agent: Agent) -> None:
        event = ActionProposed(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                "action_type": action.action_type,
                "target": action.target,
                "description": action.description,
            },
        )
        await self.event_store.append(event, actor_id=str(agent.id))
        await publish_event(event)
    
    async def _emit_preview_event(self, action: Action, preview: ActionPreview) -> None:
        event = ActionPreviewGenerated(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "risk_level": preview.risk_level.value,
                "affected_count": preview.affected_count,
                "warnings_count": len(preview.warnings),
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
    
    async def _emit_approved_event(
        self,
        action: Action,
        approver: Agent,
        comment: str | None = None,
        auto: bool = False,
    ) -> None:
        event = ActionApproved(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "approver_id": str(approver.id),
                "approver_name": approver.name,
                "auto_approved": auto,
                "comment": comment,
            },
        )
        await self.event_store.append(event, actor_id=str(approver.id))
        await publish_event(event)
    
    async def _emit_rejected_event(
        self,
        action: Action,
        rejector: Agent,
        reason: str,
    ) -> None:
        event = ActionRejected(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "rejector_id": str(rejector.id),
                "rejector_name": rejector.name,
                "reason": reason,
            },
        )
        await self.event_store.append(event, actor_id=str(rejector.id))
        await publish_event(event)
    
    async def _emit_executed_event(self, action: Action, executor: Agent) -> None:
        event = ActionExecuted(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "executor_id": str(executor.id),
            },
        )
        await self.event_store.append(event, actor_id=str(executor.id))
        await publish_event(event)
    
    async def _emit_failed_event(self, action: Action, error: str) -> None:
        event = ActionFailed(
            stream_id=f"action:{action.id}",
            data={
                "action_id": str(action.id),
                "error": error,
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
    
    async def _emit_metered_event(self, action: Action) -> None:
        event = ActionMetered(
            stream_id=f"agent:{action.agent_id}",
            data={
                "agent_id": str(action.agent_id),
                "action_id": str(action.id),
                "action_type": action.action_type,
            },
        )
        await self.event_store.append(event)
        await publish_event(event)
    
    async def _send_callback(self, action: Action, status: str) -> None:
        """Send webhook callback."""
        if not action.callback_url:
            return
        
        payload = {
            "event": f"action.{status}",
            "action_id": str(action.id),
            "status": action.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    action.callback_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            logger.debug("Callback sent", action_id=str(action.id), url=action.callback_url)
        except Exception as e:
            logger.error("Callback failed", action_id=str(action.id), error=str(e))
