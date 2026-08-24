"""Synchronous Extension-layer dispatcher for validated StreamEvent objects."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from uuid import uuid4

from core.contracts import StreamConsumer, StreamEvent

from .replay import StreamReplay


class StreamDispatchError(RuntimeError):
    """Raised after one or more subscribers fail to consume a stored event."""

    def __init__(self, event_id: str, failures: tuple[Exception, ...]) -> None:
        self.event_id = event_id
        self.failures = failures
        super().__init__(
            f"{len(failures)} subscriber(s) failed for event {event_id}"
        )


class StreamingBridge:
    """Publish, subscribe and replay StreamEvents without Runtime dependencies.

    Publication is synchronous. The event is validated and stored before a
    snapshot of subscribers is notified. A failing subscriber does not prevent
    other subscribers from receiving the event.
    """

    def __init__(self, replay_store: StreamReplay | None = None) -> None:
        self._replay_store = replay_store or StreamReplay()
        self._subscribers: dict[str, StreamConsumer] = {}
        self._lock = RLock()

    def publish(self, event: StreamEvent) -> None:
        self._replay_store.append(event)
        with self._lock:
            consumers = tuple(self._subscribers.values())
        failures: list[Exception] = []
        for consumer in consumers:
            try:
                consumer.on_event(event)
            except Exception as exc:  # subscribers are isolated from each other
                failures.append(exc)
        if failures:
            raise StreamDispatchError(event.event_id, tuple(failures))

    def subscribe(self, consumer: StreamConsumer) -> Callable[[], None]:
        if not isinstance(consumer, StreamConsumer):
            raise TypeError("consumer must implement StreamConsumer.on_event")
        subscription_id = uuid4().hex
        with self._lock:
            self._subscribers[subscription_id] = consumer

        def unsubscribe() -> None:
            with self._lock:
                self._subscribers.pop(subscription_id, None)

        return unsubscribe

    def replay(self, session_id: str) -> tuple[StreamEvent, ...]:
        return self._replay_store.replay(session_id)
