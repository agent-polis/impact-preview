"""
Event projections - handlers that update read models from events.

Projections subscribe to events and update denormalized read models
(the agents, simulations, proposals tables) for efficient querying.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.events.bus import subscribe
from agent_polis.events.types import DomainEvent

logger = structlog.get_logger()


class ProjectionHandler:
    """
    Base class for projection handlers.
    
    Projections listen to events and update read models accordingly.
    They can be replayed from the event store to rebuild read models.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def handle(self, event: DomainEvent) -> None:
        """Handle an event and update projections."""
        raise NotImplementedError


# Agent Projections
@subscribe("AgentRegistered")
async def project_agent_registered(event: DomainEvent) -> None:
    """Project AgentRegistered event to agents read model."""
    logger.info(
        "Projecting AgentRegistered",
        agent_id=event.data.get("agent_id"),
        name=event.data.get("name"),
    )
    # Note: Actual DB update happens in the service layer when creating the agent
    # This projection is for additional side effects (notifications, metrics, etc.)


@subscribe("AgentVerified")
async def project_agent_verified(event: DomainEvent) -> None:
    """Project AgentVerified event."""
    logger.info(
        "Projecting AgentVerified",
        agent_id=event.data.get("agent_id"),
        method=event.data.get("method"),
    )


@subscribe("AgentReputationChanged")
async def project_reputation_changed(event: DomainEvent) -> None:
    """Project reputation change."""
    logger.info(
        "Projecting AgentReputationChanged",
        agent_id=event.data.get("agent_id"),
        delta=event.data.get("delta"),
        new_score=event.data.get("new_score"),
    )


# Simulation Projections
@subscribe("SimulationCreated")
async def project_simulation_created(event: DomainEvent) -> None:
    """Project SimulationCreated event."""
    logger.info(
        "Projecting SimulationCreated",
        simulation_id=event.data.get("simulation_id"),
    )


@subscribe("SimulationCompleted")
async def project_simulation_completed(event: DomainEvent) -> None:
    """Project SimulationCompleted event."""
    logger.info(
        "Projecting SimulationCompleted",
        simulation_id=event.data.get("simulation_id"),
        duration_ms=event.data.get("duration_ms"),
    )


@subscribe("SimulationFailed")
async def project_simulation_failed(event: DomainEvent) -> None:
    """Project SimulationFailed event."""
    logger.warning(
        "Projecting SimulationFailed",
        simulation_id=event.data.get("simulation_id"),
        error=event.data.get("error"),
    )


# Metering Projections
@subscribe("SimulationMetered")
async def project_simulation_metered(event: DomainEvent) -> None:
    """Track simulation usage for metering."""
    logger.info(
        "Projecting SimulationMetered",
        agent_id=event.data.get("agent_id"),
        simulation_id=event.data.get("simulation_id"),
        cost_credits=event.data.get("cost_credits"),
    )


async def rebuild_projections(session: AsyncSession, stream_id: str) -> None:
    """
    Rebuild projections for a stream by replaying all its events.
    
    This is useful for:
    - Fixing corrupted read models
    - Adding new projections after the fact
    - Migrating data
    """
    from agent_polis.events.store import EventStore
    from agent_polis.events.bus import publish_event
    
    store = EventStore(session)
    events = await store.get_stream(stream_id)
    
    logger.info(
        "Rebuilding projections",
        stream_id=stream_id,
        event_count=len(events),
    )
    
    for event in events:
        # Convert DB event to domain event and republish
        from agent_polis.events.types import deserialize_event
        domain_event = deserialize_event(
            event.event_type,
            {
                "stream_id": event.stream_id,
                "data": event.event_data,
                "metadata": event.event_metadata,
            }
        )
        await publish_event(domain_event)
    
    logger.info("Projection rebuild complete", stream_id=stream_id)
