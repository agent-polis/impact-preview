"""
Agent management API routes.
"""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.agents.models import (
    AgentCreate,
    AgentListResponse,
    AgentProfile,
    AgentResponse,
    AgentStats,
    AgentUpdate,
)
from agent_polis.agents.service import AgentService
from agent_polis.config import settings
from agent_polis.shared.db import get_db
from agent_polis.shared.security import CurrentAgent

logger = structlog.get_logger()
router = APIRouter()


@router.post("/register", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    data: AgentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentResponse:
    """
    Register a new agent with the polis.
    
    Returns an API key that must be saved - it won't be shown again.
    Use this API key in the X-API-Key header for authenticated requests.
    """
    service = AgentService(db)
    
    try:
        agent, api_key = await service.register(data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        api_key=api_key,
        status=agent.status,
        created_at=agent.created_at,
    )


@router.get("/me", response_model=AgentProfile)
async def get_current_agent(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentProfile:
    """Get the current authenticated agent's profile."""
    service = AgentService(db)
    return await service.get_profile(agent)


@router.get("/me/stats", response_model=AgentStats)
async def get_current_agent_stats(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentStats:
    """Get the current agent's usage statistics."""
    service = AgentService(db)
    return await service.get_stats(
        agent,
        monthly_limit=settings.free_tier_simulations_per_month,
    )


@router.patch("/me", response_model=AgentProfile)
async def update_current_agent(
    data: AgentUpdate,
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentProfile:
    """Update the current agent's profile."""
    if data.description is not None:
        agent.description = data.description
    
    await db.flush()
    
    service = AgentService(db)
    return await service.get_profile(agent)


@router.post("/me/regenerate-key")
async def regenerate_api_key(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Regenerate the current agent's API key.
    
    The old key will be immediately invalidated.
    Returns the new API key - save it, it won't be shown again!
    """
    from agent_polis.shared.security import generate_api_key, hash_api_key
    
    new_api_key = generate_api_key()
    agent.api_key_hash = hash_api_key(new_api_key)
    
    await db.flush()
    
    logger.info("API key regenerated", agent_id=str(agent.id), agent_name=agent.name)
    
    return {
        "message": "API key regenerated successfully",
        "api_key": new_api_key,
        "warning": "Save this key - it won't be shown again!",
    }


@router.delete("/me")
async def deactivate_agent(
    agent: CurrentAgent,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """
    Deactivate the current agent's account.
    
    This sets the agent status to 'inactive'. The agent can be reactivated
    by contacting support.
    """
    agent.status = "inactive"
    await db.flush()
    
    logger.info("Agent deactivated", agent_id=str(agent.id), agent_name=agent.name)
    
    return {
        "message": "Agent deactivated successfully",
        "status": "inactive",
    }


@router.get("/{name}", response_model=AgentProfile)
async def get_agent_by_name(
    name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AgentProfile:
    """Get a public agent profile by name."""
    service = AgentService(db)
    agent = await service.get_by_name(name)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{name}' not found",
        )
    
    return await service.get_profile(agent)


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
) -> AgentListResponse:
    """List registered agents with pagination."""
    service = AgentService(db)
    profiles, total = await service.list_agents(
        page=page,
        page_size=page_size,
        status=status_filter,
    )
    
    return AgentListResponse(
        agents=profiles,
        total=total,
        page=page,
        page_size=page_size,
    )
