"""
In-process event bus for publishing and subscribing to domain events.

This enables loose coupling between modules - the event store persists events,
and the bus notifies interested subscribers (e.g., projection handlers).
"""

import asyncio
from collections import defaultdict
from typing import Callable, Coroutine, Any

import structlog

from agent_polis.events.types import DomainEvent

logger = structlog.get_logger()

# Type alias for event handlers
EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class EventBus:
    """
    Simple in-process event bus for domain events.
    
    Subscribers register handlers for specific event types. When an event
    is published, all registered handlers are called asynchronously.
    
    For production scaling, this could be replaced with Redis pub/sub
    or a dedicated message broker.
    """
    
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Event type to subscribe to (e.g., "AgentRegistered")
            handler: Async function to call when event is published
        """
        self._handlers[event_type].append(handler)
        logger.debug("Handler subscribed", event_type=event_type, handler=handler.__name__)
    
    def subscribe_all(self, handler: EventHandler) -> None:
        """
        Subscribe to all events.
        
        Args:
            handler: Async function to call for every event
        """
        self._global_handlers.append(handler)
        logger.debug("Global handler subscribed", handler=handler.__name__)
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    async def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all subscribers.
        
        Handlers are called concurrently. Exceptions in handlers are logged
        but don't prevent other handlers from running.
        
        Args:
            event: Domain event to publish
        """
        handlers = self._handlers.get(event.event_type, []) + self._global_handlers
        
        if not handlers:
            logger.debug("No handlers for event", event_type=event.event_type)
            return
        
        logger.debug(
            "Publishing event",
            event_type=event.event_type,
            handler_count=len(handlers),
        )
        
        # Run all handlers concurrently
        tasks = [self._safe_call(handler, event) for handler in handlers]
        await asyncio.gather(*tasks)
    
    async def _safe_call(self, handler: EventHandler, event: DomainEvent) -> None:
        """Call a handler with error handling."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                "Event handler failed",
                event_type=event.event_type,
                handler=handler.__name__,
                error=str(e),
                exc_info=e,
            )


# Global event bus instance
_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return _event_bus


async def publish_event(event: DomainEvent) -> None:
    """Publish an event to the global bus."""
    await _event_bus.publish(event)


def subscribe(event_type: str) -> Callable[[EventHandler], EventHandler]:
    """
    Decorator to subscribe a function to an event type.
    
    Usage:
        @subscribe("AgentRegistered")
        async def handle_agent_registered(event: DomainEvent):
            ...
    """
    def decorator(handler: EventHandler) -> EventHandler:
        _event_bus.subscribe(event_type, handler)
        return handler
    return decorator
