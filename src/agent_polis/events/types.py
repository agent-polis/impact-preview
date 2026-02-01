"""
Domain event type definitions.

All events in the system inherit from DomainEvent and are immutable records
of something that happened.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """
    Base class for all domain events.
    
    Events are immutable records of things that happened. They form the
    append-only audit trail that is the source of truth for system state.
    """
    
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: str = Field(description="Event type name (e.g., 'AgentRegistered')")
    stream_id: str = Field(description="Aggregate/stream identifier (e.g., 'agent:abc123')")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When event occurred")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata (actor, correlation, etc.)")

    class Config:
        frozen = True  # Make events immutable


# Agent Events
class AgentRegistered(DomainEvent):
    """An agent registered with the polis."""
    event_type: str = "AgentRegistered"


class AgentVerified(DomainEvent):
    """An agent was verified (KYA check passed)."""
    event_type: str = "AgentVerified"


class AgentSuspended(DomainEvent):
    """An agent was suspended."""
    event_type: str = "AgentSuspended"


class AgentReputationChanged(DomainEvent):
    """An agent's reputation score changed."""
    event_type: str = "AgentReputationChanged"


# Outcome Tracking Events (works with both actions and legacy simulations)
class OutcomePredicted(DomainEvent):
    """An outcome prediction was recorded."""
    event_type: str = "OutcomePredicted"


class OutcomeActualized(DomainEvent):
    """The actual outcome was recorded, to compare with prediction."""
    event_type: str = "OutcomeActualized"


# Action Events (v0.2 - Impact Preview)
class ActionProposed(DomainEvent):
    """An action was proposed by an agent, awaiting approval."""
    event_type: str = "ActionProposed"


class ActionPreviewGenerated(DomainEvent):
    """Impact preview was generated for a proposed action."""
    event_type: str = "ActionPreviewGenerated"


class ActionApproved(DomainEvent):
    """A proposed action was approved by a human."""
    event_type: str = "ActionApproved"


class ActionRejected(DomainEvent):
    """A proposed action was rejected by a human."""
    event_type: str = "ActionRejected"


class ActionModified(DomainEvent):
    """A proposed action was modified before approval."""
    event_type: str = "ActionModified"


class ActionExecuted(DomainEvent):
    """An approved action was executed."""
    event_type: str = "ActionExecuted"


class ActionFailed(DomainEvent):
    """An action execution failed."""
    event_type: str = "ActionFailed"


class ActionTimedOut(DomainEvent):
    """A proposed action timed out waiting for approval."""
    event_type: str = "ActionTimedOut"


# Metering Events
class ActionMetered(DomainEvent):
    """An action preview/execution was metered for billing/limits."""
    event_type: str = "ActionMetered"


# Legacy Events (kept for backward compatibility with v0.1)
class SimulationCreated(DomainEvent):
    """[LEGACY] A simulation scenario was created."""
    event_type: str = "SimulationCreated"


class SimulationStarted(DomainEvent):
    """[LEGACY] A simulation execution started."""
    event_type: str = "SimulationStarted"


class SimulationCompleted(DomainEvent):
    """[LEGACY] A simulation execution completed."""
    event_type: str = "SimulationCompleted"


class SimulationFailed(DomainEvent):
    """[LEGACY] A simulation execution failed."""
    event_type: str = "SimulationFailed"


class SimulationMetered(DomainEvent):
    """[LEGACY] A simulation was metered for billing/limits."""
    event_type: str = "SimulationMetered"


# Event type registry for deserialization
EVENT_TYPES: dict[str, type[DomainEvent]] = {
    # Agent events
    "AgentRegistered": AgentRegistered,
    "AgentVerified": AgentVerified,
    "AgentSuspended": AgentSuspended,
    "AgentReputationChanged": AgentReputationChanged,
    # Action events (v0.2 - Impact Preview)
    "ActionProposed": ActionProposed,
    "ActionPreviewGenerated": ActionPreviewGenerated,
    "ActionApproved": ActionApproved,
    "ActionRejected": ActionRejected,
    "ActionModified": ActionModified,
    "ActionExecuted": ActionExecuted,
    "ActionFailed": ActionFailed,
    "ActionTimedOut": ActionTimedOut,
    "ActionMetered": ActionMetered,
    # Outcome tracking
    "OutcomePredicted": OutcomePredicted,
    "OutcomeActualized": OutcomeActualized,
    # Legacy simulation events (v0.1 compatibility)
    "SimulationCreated": SimulationCreated,
    "SimulationStarted": SimulationStarted,
    "SimulationCompleted": SimulationCompleted,
    "SimulationFailed": SimulationFailed,
    "SimulationMetered": SimulationMetered,
}


def deserialize_event(event_type: str, data: dict) -> DomainEvent:
    """Deserialize an event from stored data."""
    event_class = EVENT_TYPES.get(event_type, DomainEvent)
    return event_class(**data)
