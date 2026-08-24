"""Simple offline consumer used by tests, Console prototypes and diagnostics."""

from __future__ import annotations

from threading import RLock

from core.contracts import StreamEvent


class StreamCollector:
    """Collect events in delivery order without performing external I/O."""

    def __init__(self) -> None:
        self._events: list[StreamEvent] = []
        self._lock = RLock()

    def on_event(self, event: StreamEvent) -> None:
        if not isinstance(event, StreamEvent):
            raise TypeError("event must be a StreamEvent")
        with self._lock:
            self._events.append(event)

    @property
    def events(self) -> tuple[StreamEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def replay(self, session_id: str) -> tuple[StreamEvent, ...]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            return tuple(
                event for event in self._events if event.session_id == session_id
            )

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
