"""
SQLAlchemy model for the event store table.

Events are stored in an append-only table with hash chaining for tamper detection.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from agent_polis.shared.db import Base, JSONType


class Event(Base):
    """
    Event store table - append-only, immutable record of all domain events.
    
    Each event includes a hash of itself and the previous event's hash,
    creating a tamper-evident chain similar to a blockchain.
    """
    
    __tablename__ = "events"
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Stream identification (e.g., "agent:abc123", "simulation:xyz789")
    stream_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stream_version: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Event type and data
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    
    # Event metadata (actor, timestamp, correlation ID, etc.)
    # Note: called event_metadata to avoid conflict with SQLAlchemy's reserved 'metadata'
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    # Hash chain for tamper detection
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("stream_id", "stream_version", name="uq_stream_version"),
        Index("idx_events_stream_version", "stream_id", "stream_version"),
        Index("idx_events_created_at", "created_at"),
    )
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of this event including the previous hash.
        
        This creates a tamper-evident chain - if any event is modified,
        all subsequent hashes become invalid.
        """
        content = f"{self.stream_id}:{self.stream_version}:{self.event_type}:{self.event_data}:{self.prev_hash or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        stream_version: int,
        event_type: str,
        event_data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        prev_hash: str | None = None,
    ) -> "Event":
        """
        Create a new event with computed hash.
        
        Args:
            stream_id: Aggregate/stream identifier
            stream_version: Version number within the stream
            event_type: Type of event (e.g., "AgentRegistered")
            event_data: Event payload
            metadata: Optional metadata (actor, correlation ID, etc.)
            prev_hash: Hash of the previous event in the stream
            
        Returns:
            New Event instance with computed hash
        """
        event = cls(
            stream_id=stream_id,
            stream_version=stream_version,
            event_type=event_type,
            event_data=event_data,
            event_metadata=metadata or {},
            prev_hash=prev_hash,
        )
        event.hash = event.compute_hash()
        return event
    
    def verify_hash(self) -> bool:
        """Verify that the stored hash matches the computed hash."""
        return self.hash == self.compute_hash()
    
    def __repr__(self) -> str:
        return f"<Event {self.event_type} stream={self.stream_id} v={self.stream_version}>"
