"""
A2A Protocol API routes.

Implements the A2A task management endpoints for agent-to-agent communication.
"""

from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.a2a.models import (
    A2AErrorCode,
    Message,
    MessagePart,
    Task,
    TaskRequest,
    TaskResponse,
    TaskStatus,
)
from agent_polis.a2a.task_store import TaskStore, get_task_store
from agent_polis.shared.db import get_db

logger = structlog.get_logger()
router = APIRouter()


def json_rpc_error(request_id: str, code: int, message: str, data: Any = None) -> TaskResponse:
    """Create a JSON-RPC error response."""
    error = {"code": code, "message": message}
    if data:
        error["data"] = data
    return TaskResponse(id=request_id, error=error)


def json_rpc_success(request_id: str, result: Any) -> TaskResponse:
    """Create a JSON-RPC success response."""
    return TaskResponse(id=request_id, result=result)


@router.post("/tasks/send", response_model=TaskResponse)
async def send_task(
    request: TaskRequest,
    task_store: Annotated[TaskStore, Depends(get_task_store)],
) -> TaskResponse:
    """
    Send a message/task to this agent.
    
    This is the main A2A endpoint for agent-to-agent communication.
    Other agents send tasks here, and we process them and return results.
    """
    try:
        params = request.params
        message_data = params.get("message", {})
        task_id = params.get("task_id")
        
        # Parse message
        message = Message(
            role=message_data.get("role", "user"),
            parts=[MessagePart(**p) for p in message_data.get("parts", [])],
            message_id=message_data.get("messageId", uuid4().hex),
        )
        
        if task_id:
            # Continue existing task
            task = await task_store.get(task_id)
            if not task:
                return json_rpc_error(
                    request.id,
                    A2AErrorCode.TASK_NOT_FOUND,
                    f"Task {task_id} not found",
                )
            task.messages.append(message)
        else:
            # Create new task
            task = Task(messages=[message])
            await task_store.save(task)
        
        # Process the task (for now, just acknowledge receipt)
        # In the full implementation, this would route to simulation/governance handlers
        task.status = TaskStatus.WORKING
        await task_store.save(task)
        
        # Generate response
        response_message = await process_task_message(task, message)
        task.messages.append(response_message)
        
        # Mark as completed for simple requests
        task.status = TaskStatus.COMPLETED
        task.result = {"acknowledged": True}
        await task_store.save(task)
        
        logger.info(
            "Task processed",
            task_id=task.id,
            status=task.status,
            message_count=len(task.messages),
        )
        
        return json_rpc_success(
            request.id,
            {
                "task": {
                    "id": task.id,
                    "status": task.status,
                },
                "message": response_message.model_dump(),
            },
        )
        
    except Exception as e:
        logger.error("Task processing failed", error=str(e), exc_info=e)
        return json_rpc_error(
            request.id,
            A2AErrorCode.INTERNAL_ERROR,
            str(e),
        )


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    task_store: Annotated[TaskStore, Depends(get_task_store)],
) -> dict:
    """Get task status and details."""
    task = await task_store.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    return {
        "id": task.id,
        "status": task.status,
        "messages": [m.model_dump() for m in task.messages],
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "result": task.result,
        "error": task.error,
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    task_store: Annotated[TaskStore, Depends(get_task_store)],
) -> dict:
    """Cancel a running task."""
    task = await task_store.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task already {task.status}",
        )
    
    task.status = TaskStatus.CANCELED
    await task_store.save(task)
    
    logger.info("Task canceled", task_id=task_id)
    
    return {"id": task.id, "status": task.status}


async def process_task_message(task: Task, message: Message) -> Message:
    """
    Process an incoming message and generate a response.
    
    This is where we route messages to appropriate handlers:
    - Simulation requests go to the simulation module
    - Governance requests go to the governance module
    - General queries get a help response
    """
    # Extract text from message parts
    text_parts = [p.text for p in message.parts if p.kind == "text" and p.text]
    text = " ".join(text_parts).lower() if text_parts else ""
    
    # Simple routing logic (will be expanded)
    if "simulate" in text or "simulation" in text:
        response_text = (
            "I can help you run a simulation. To create a simulation, "
            "use the POST /api/v1/simulations endpoint with your scenario definition. "
            "Once created, use POST /api/v1/simulations/{id}/run to execute it."
        )
    elif "proposal" in text or "governance" in text:
        response_text = (
            "Governance features (proposals, voting) are coming in Phase 2. "
            "Currently, you can use the simulation features to test scenarios "
            "before committing to them."
        )
    elif "help" in text or not text:
        response_text = (
            "I'm Agent Polis, a governance and coordination layer for AI agents. "
            "I offer:\n"
            "- Simulation: Test scenarios in a sandbox before committing\n"
            "- Coordination: Coming soon - proposals, voting, governance\n\n"
            "Use GET /.well-known/agent.json to see my full capabilities."
        )
    else:
        response_text = (
            f"I received your message about '{text[:100]}...'. "
            "I can help with simulations and (soon) governance. "
            "Send 'help' for more information."
        )
    
    return Message(
        role="agent",
        parts=[MessagePart(kind="text", text=response_text)],
    )
