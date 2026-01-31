"""
Pydantic models for simulation API.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SimulationStatus(str, Enum):
    """Simulation execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ScenarioDefinition(BaseModel):
    """
    Definition of a simulation scenario.
    
    A scenario describes what to simulate - the code/plan to run,
    the inputs, and the expected behavior.
    """
    
    name: str = Field(
        max_length=200,
        description="Human-readable scenario name",
    )
    
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Detailed description of the scenario",
    )
    
    # What to execute
    code: str | None = Field(
        default=None,
        max_length=50000,  # 50KB limit
        description="Python code to execute in sandbox (max 50KB)",
    )
    
    script_url: str | None = Field(
        default=None,
        description="URL to script to fetch and execute",
    )
    
    # Inputs and environment
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the simulation",
    )
    
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the sandbox",
    )
    
    # Execution constraints
    timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Maximum execution time in seconds",
    )
    
    # Optional: expected outcomes for comparison
    expected_outcomes: dict[str, Any] | None = Field(
        default=None,
        description="Expected results for validation",
    )


class SimulationCreate(BaseModel):
    """Request model for creating a simulation."""
    
    scenario: ScenarioDefinition = Field(
        description="The scenario to simulate",
    )
    
    proposal_id: UUID | None = Field(
        default=None,
        description="Optional linked proposal ID (for governance integration)",
    )
    
    callback_url: str | None = Field(
        default=None,
        max_length=500,
        description="Optional webhook URL to call when simulation completes",
    )


class SimulationRunRequest(BaseModel):
    """Request model for running a simulation."""
    
    # Optional overrides
    timeout_override: int | None = Field(
        default=None,
        ge=1,
        le=300,
        description="Override timeout for this run",
    )
    
    input_overrides: dict[str, Any] | None = Field(
        default=None,
        description="Override inputs for this run",
    )


class ExecutionLog(BaseModel):
    """A log entry from simulation execution."""
    
    timestamp: datetime
    level: str  # info, warning, error
    message: str
    source: str = "sandbox"  # sandbox, system, user


class SimulationResult(BaseModel):
    """Results from a completed simulation."""
    
    success: bool = Field(description="Whether execution completed without errors")
    
    output: Any | None = Field(
        default=None,
        description="Returned output from the simulation",
    )
    
    stdout: str | None = Field(
        default=None,
        description="Standard output captured",
    )
    
    stderr: str | None = Field(
        default=None,
        description="Standard error captured",
    )
    
    exit_code: int | None = Field(
        default=None,
        description="Process exit code",
    )
    
    duration_ms: int | None = Field(
        default=None,
        description="Execution duration in milliseconds",
    )
    
    logs: list[ExecutionLog] = Field(
        default_factory=list,
        description="Execution logs",
    )
    
    error: str | None = Field(
        default=None,
        description="Error message if failed",
    )


class OutcomePrediction(BaseModel):
    """A prediction about the simulation outcome."""
    
    predicted_success: bool = Field(
        description="Whether the simulation is expected to succeed",
    )
    
    predicted_output: Any | None = Field(
        default=None,
        description="Expected output value",
    )
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in prediction (0-1)",
    )
    
    rationale: str | None = Field(
        default=None,
        max_length=500,
        description="Explanation for the prediction",
    )


class SimulationResponse(BaseModel):
    """Response model for simulation operations."""
    
    id: UUID
    creator_id: UUID
    proposal_id: UUID | None
    status: SimulationStatus
    scenario: ScenarioDefinition
    result: SimulationResult | None
    prediction: OutcomePrediction | None
    actual_outcome: dict[str, Any] | None
    e2b_sandbox_id: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    class Config:
        from_attributes = True


class SimulationListResponse(BaseModel):
    """Response for listing simulations."""
    
    simulations: list[SimulationResponse]
    total: int
    page: int
    page_size: int
