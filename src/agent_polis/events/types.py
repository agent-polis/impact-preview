"""
Domain event type definitions.

All events in the system inherit from DomainEvent and are immutable records
of something that happened.
"""

from datetime import datetime
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
    occurred_at: datetime = Field(default_factory=datetime.utcnow, description="When event occurred")
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


# Simulation Events
class SimulationCreated(DomainEvent):
    """A simulation scenario was created."""
    event_type: str = "SimulationCreated"


class SimulationStarted(DomainEvent):
    """A simulation execution started."""
    event_type: str = "SimulationStarted"


class SimulationCompleted(DomainEvent):
    """A simulation execution completed."""
    event_type: str = "SimulationCompleted"


class SimulationFailed(DomainEvent):
    """A simulation execution failed."""
    event_type: str = "SimulationFailed"


class OutcomePredicted(DomainEvent):
    """An outcome prediction was recorded for a simulation."""
    event_type: str = "OutcomePredicted"


class OutcomeActualized(DomainEvent):
    """The actual outcome was recorded, to compare with prediction."""
    event_type: str = "OutcomeActualized"


# Governance Events (Phase 2)
class ProposalCreated(DomainEvent):
    """A proposal was created."""
    event_type: str = "ProposalCreated"


class VoteCast(DomainEvent):
    """A vote was cast on a proposal."""
    event_type: str = "VoteCast"


class ProposalResolved(DomainEvent):
    """A proposal voting concluded with a result."""
    event_type: str = "ProposalResolved"


# Metering Events
class SimulationMetered(DomainEvent):
    """A simulation was metered for billing/limits."""
    event_type: str = "SimulationMetered"


# Event type registry for deserialization
EVENT_TYPES: dict[str, type[DomainEvent]] = {
    "AgentRegistered": AgentRegistered,
    "AgentVerified": AgentVerified,
    "AgentSuspended": AgentSuspended,
    "AgentReputationChanged": AgentReputationChanged,
    "SimulationCreated": SimulationCreated,
    "SimulationStarted": SimulationStarted,
    "SimulationCompleted": SimulationCompleted,
    "SimulationFailed": SimulationFailed,
    "OutcomePredicted": OutcomePredicted,
    "OutcomeActualized": OutcomeActualized,
    "ProposalCreated": ProposalCreated,
    "VoteCast": VoteCast,
    "ProposalResolved": ProposalResolved,
    "SimulationMetered": SimulationMetered,
}


def deserialize_event(event_type: str, data: dict) -> DomainEvent:
    """Deserialize an event from stored data."""
    event_class = EVENT_TYPES.get(event_type, DomainEvent)
    return event_class(**data)
