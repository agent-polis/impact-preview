"""
Pydantic models for agent management API.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import re


class AgentCreate(BaseModel):
    """Request model for agent registration."""
    
    name: str = Field(
        min_length=3,
        max_length=50,
        description="Unique agent name (alphanumeric and hyphens only)",
    )
    description: str = Field(
        max_length=500,
        description="Brief description of the agent",
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name format."""
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9-]*$", v):
            raise ValueError(
                "Name must start with a letter and contain only letters, numbers, and hyphens"
            )
        return v.lower()


class AgentResponse(BaseModel):
    """Response model for agent registration."""
    
    id: UUID
    name: str
    description: str
    api_key: str = Field(
        description="API key for authentication - SAVE THIS, it won't be shown again!"
    )
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class AgentProfile(BaseModel):
    """Public agent profile."""
    
    id: UUID
    name: str
    description: str
    reputation_score: float
    verified: bool
    verification_method: str | None
    status: str
    created_at: datetime
    last_active_at: datetime | None
    simulation_count: int = 0
    
    class Config:
        from_attributes = True


class AgentUpdate(BaseModel):
    """Request model for updating agent profile."""
    
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated description",
    )


class AgentStats(BaseModel):
    """Agent usage statistics."""
    
    total_simulations: int
    successful_simulations: int
    failed_simulations: int
    prediction_accuracy: float | None
    simulations_this_month: int
    monthly_limit: int


class AgentListResponse(BaseModel):
    """Response for listing agents."""
    
    agents: list[AgentProfile]
    total: int
    page: int
    page_size: int
