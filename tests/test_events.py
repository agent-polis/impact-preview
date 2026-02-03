"""
Event sourcing infrastructure tests.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_polis.events.bus import EventBus
from agent_polis.events.store import EventStore
from agent_polis.events.types import AgentRegistered, DomainEvent


@pytest.mark.asyncio
async def test_event_append(test_session: AsyncSession):
    """Test appending events to the store."""
    store = EventStore(test_session)

    event = AgentRegistered(
        stream_id="agent:test-123",
        data={
            "agent_id": "test-123",
            "name": "test-agent",
            "description": "Test agent",
        },
    )

    db_event = await store.append(event)
    await test_session.commit()

    assert db_event.stream_id == "agent:test-123"
    assert db_event.event_type == "AgentRegistered"
    assert db_event.stream_version == 1
    assert db_event.hash is not None


@pytest.mark.asyncio
async def test_event_versioning(test_session: AsyncSession):
    """Test that event versions increment correctly."""
    store = EventStore(test_session)
    stream_id = "agent:version-test"

    # Append multiple events
    for i in range(3):
        event = DomainEvent(
            stream_id=stream_id,
            event_type="TestEvent",
            data={"index": i},
        )
        db_event = await store.append(event)
        assert db_event.stream_version == i + 1

    await test_session.commit()

    # Verify all events
    events = await store.get_stream(stream_id)
    assert len(events) == 3
    assert [e.stream_version for e in events] == [1, 2, 3]


@pytest.mark.asyncio
async def test_event_hash_chain(test_session: AsyncSession):
    """Test hash chain integrity."""
    store = EventStore(test_session)
    stream_id = "agent:hash-test"

    # Create chain of events
    for i in range(3):
        event = DomainEvent(
            stream_id=stream_id,
            event_type="ChainEvent",
            data={"index": i},
        )
        await store.append(event)

    await test_session.commit()

    # Verify chain
    events = await store.get_stream(stream_id)

    # First event has no prev_hash
    assert events[0].prev_hash is None

    # Each subsequent event's prev_hash matches previous event's hash
    for i in range(1, len(events)):
        assert events[i].prev_hash == events[i-1].hash


@pytest.mark.asyncio
async def test_stream_integrity_verification(test_session: AsyncSession):
    """Test stream integrity verification."""
    store = EventStore(test_session)
    stream_id = "agent:integrity-test"

    # Create events
    for i in range(3):
        event = DomainEvent(
            stream_id=stream_id,
            event_type="IntegrityEvent",
            data={"index": i},
        )
        await store.append(event)

    await test_session.commit()

    # Verify integrity
    is_valid = await store.verify_stream_integrity(stream_id)
    assert is_valid is True


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    """Test event bus publish/subscribe."""
    bus = EventBus()
    received_events = []

    async def handler(event: DomainEvent):
        received_events.append(event)

    # Subscribe
    bus.subscribe("TestEvent", handler)

    # Publish
    event = DomainEvent(
        stream_id="test:bus",
        event_type="TestEvent",
        data={"message": "hello"},
    )
    await bus.publish(event)

    # Verify
    assert len(received_events) == 1
    assert received_events[0].data["message"] == "hello"


@pytest.mark.asyncio
async def test_event_bus_global_handler():
    """Test event bus global (all events) handler."""
    bus = EventBus()
    received = []

    async def global_handler(event: DomainEvent):
        received.append(event.event_type)

    bus.subscribe_all(global_handler)

    # Publish different event types
    for event_type in ["EventA", "EventB", "EventC"]:
        event = DomainEvent(
            stream_id="test:global",
            event_type=event_type,
            data={},
        )
        await bus.publish(event)

    assert received == ["EventA", "EventB", "EventC"]
