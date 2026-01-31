"""
Event store implementation for appending and reading events.

The event store is append-only - events cannot be modified or deleted.
This provides an immutable audit trail of all system activity.
"""

from typing import Sequence
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.events.models import Event
from agent_polis.events.types import DomainEvent

logger = structlog.get_logger()


class EventStore:
    """
    Event store for persisting and retrieving domain events.
    
    The store ensures:
    - Append-only semantics (no updates or deletes)
    - Optimistic concurrency via stream versioning
    - Tamper detection via hash chaining
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def append(
        self,
        event: DomainEvent,
        actor_id: str | None = None,
        correlation_id: str | None = None,
    ) -> Event:
        """
        Append an event to the store.
        
        Args:
            event: Domain event to append
            actor_id: Optional ID of the agent/user who caused this event
            correlation_id: Optional ID for correlating related events
            
        Returns:
            The persisted Event record
            
        Raises:
            IntegrityError: If stream version conflict (optimistic concurrency)
        """
        # Get current stream version and last hash
        result = await self.session.execute(
            select(Event.stream_version, Event.hash)
            .where(Event.stream_id == event.stream_id)
            .order_by(Event.stream_version.desc())
            .limit(1)
        )
        row = result.first()
        
        if row:
            next_version = row.stream_version + 1
            prev_hash = row.hash
        else:
            next_version = 1
            prev_hash = None
        
        # Build metadata
        metadata = {
            **event.metadata,
            "event_id": str(event.event_id),
            "occurred_at": event.occurred_at.isoformat(),
        }
        if actor_id:
            metadata["actor_id"] = actor_id
        if correlation_id:
            metadata["correlation_id"] = correlation_id
        
        # Create and persist the event record
        db_event = Event.create(
            stream_id=event.stream_id,
            stream_version=next_version,
            event_type=event.event_type,
            event_data=event.data,
            metadata=metadata,
            prev_hash=prev_hash,
        )
        
        self.session.add(db_event)
        await self.session.flush()
        
        logger.info(
            "Event appended",
            event_type=event.event_type,
            stream_id=event.stream_id,
            version=next_version,
        )
        
        return db_event
    
    async def get_stream(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> Sequence[Event]:
        """
        Get all events for a stream, optionally from a specific version.
        
        Args:
            stream_id: Stream identifier
            from_version: Start from this version (exclusive)
            
        Returns:
            List of events in version order
        """
        result = await self.session.execute(
            select(Event)
            .where(Event.stream_id == stream_id)
            .where(Event.stream_version > from_version)
            .order_by(Event.stream_version)
        )
        return result.scalars().all()
    
    async def get_by_type(
        self,
        event_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Event]:
        """
        Get events by type across all streams.
        
        Args:
            event_type: Event type to filter by
            limit: Maximum events to return
            offset: Pagination offset
            
        Returns:
            List of matching events
        """
        result = await self.session.execute(
            select(Event)
            .where(Event.event_type == event_type)
            .order_by(Event.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
    
    async def get_recent(
        self,
        limit: int = 50,
    ) -> Sequence[Event]:
        """Get most recent events across all streams."""
        result = await self.session.execute(
            select(Event)
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def verify_stream_integrity(self, stream_id: str) -> bool:
        """
        Verify hash chain integrity for a stream.
        
        Returns True if all hashes are valid, False if tampering detected.
        """
        events = await self.get_stream(stream_id)
        
        prev_hash = None
        for event in events:
            # Check prev_hash chain
            if event.prev_hash != prev_hash:
                logger.error(
                    "Hash chain broken",
                    stream_id=stream_id,
                    version=event.stream_version,
                    expected_prev=prev_hash,
                    actual_prev=event.prev_hash,
                )
                return False
            
            # Verify event hash
            if not event.verify_hash():
                logger.error(
                    "Event hash invalid",
                    stream_id=stream_id,
                    version=event.stream_version,
                )
                return False
            
            prev_hash = event.hash
        
        return True
    
    async def count_by_type(self, event_type: str) -> int:
        """Count events of a specific type."""
        result = await self.session.execute(
            select(func.count(Event.id))
            .where(Event.event_type == event_type)
        )
        return result.scalar() or 0


# Convenience functions for dependency injection
async def append_event(
    session: AsyncSession,
    event: DomainEvent,
    actor_id: str | None = None,
) -> Event:
    """Append an event using the provided session."""
    store = EventStore(session)
    return await store.append(event, actor_id=actor_id)


async def get_events(
    session: AsyncSession,
    stream_id: str,
) -> Sequence[Event]:
    """Get events for a stream using the provided session."""
    store = EventStore(session)
    return await store.get_stream(stream_id)
