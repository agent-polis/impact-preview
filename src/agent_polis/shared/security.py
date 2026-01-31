"""
Security utilities for authentication and authorization.
"""

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.shared.db import get_db

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"ap_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def get_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
) -> str:
    """
    Extract and validate API key from request header.
    
    Raises:
        HTTPException: If API key is missing
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


async def verify_api_key(
    api_key: Annotated[str, Depends(get_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> "Agent":
    """
    Verify API key and return the associated agent.
    
    Raises:
        HTTPException: If API key is invalid or agent is not active
    """
    from agent_polis.agents.db_models import Agent
    
    key_hash = hash_api_key(api_key)
    
    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == key_hash)
    )
    agent = result.scalar_one_or_none()
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if agent.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent is {agent.status}",
        )
    
    return agent


# Type alias for dependency injection
CurrentAgent = Annotated["Agent", Depends(verify_api_key)]
