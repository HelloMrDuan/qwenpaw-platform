"""Thread-safe Event Trace correlation for Extension observations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping

from core.contracts import StreamEvent

from .models import ExtensionTraceEvent, require_text, utc_timestamp


Clock = Callable[[], datetime]


class ExtensionTraceStore:
    """Associate generic or Stream events through trace_id without publishing them."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._events: list[ExtensionTraceEvent] = []
        self._by_trace: dict[str, list[ExtensionTraceEvent]] = defaultdict(list)
        self._by_extension: dict[str, list[ExtensionTraceEvent]] = defaultdict(list)
        self._event_keys: set[tuple[str, str]] = set()
        self._lock = RLock()

    def record(
        self,
        extension_name: str,
        *,
        trace_id: str,
        event_id: str,
        event_type: str,
        session_id: str | None = None,
        sequence: int | None = None,
        metadata: Mapping[str, Any] | None = None,
        observed_at: datetime | str | None = None,
    ) -> ExtensionTraceEvent:
        event = ExtensionTraceEvent(
            extension_name=extension_name,
            trace_id=trace_id,
            event_id=event_id,
            event_type=event_type,
            session_id=session_id,
            sequence=sequence,
            metadata=metadata or {},
            observed_at=utc_timestamp(
                self._clock() if observed_at is None else observed_at
            ),
        )
        key = (event.extension_name, event.event_id)
        with self._lock:
            if key in self._event_keys:
                raise ValueError(
                    "event_id must be unique within one Extension observation stream"
                )
            self._event_keys.add(key)
            self._events.append(event)
            self._by_trace[event.trace_id].append(event)
            self._by_extension[event.extension_name].append(event)
        return event

    def record_stream_event(
        self, extension_name: str, event: StreamEvent
    ) -> ExtensionTraceEvent:
        if not isinstance(event, StreamEvent):
            raise TypeError("event must be a StreamEvent")
        return self.record(
            extension_name,
            trace_id=event.trace_id,
            event_id=event.event_id,
            event_type=event.event.value,
            session_id=event.session_id,
            sequence=event.sequence,
            observed_at=event.timestamp,
            metadata={
                "stream_id": event.stream_id,
                "conversation_id": event.conversation_id,
                "task_id": event.task_id,
                "source_type": event.source.type,
                "source_name": event.source.name,
            },
        )

    def trace(
        self, trace_id: str, *, extension_name: str | None = None
    ) -> tuple[ExtensionTraceEvent, ...]:
        trace = require_text(trace_id, "trace_id")
        if extension_name is not None:
            name = require_text(extension_name, "extension_name")
        else:
            name = None
        with self._lock:
            events = tuple(self._by_trace.get(trace, ()))
        if name is None:
            return events
        return tuple(event for event in events if event.extension_name == name)

    def for_extension(self, extension_name: str) -> tuple[ExtensionTraceEvent, ...]:
        name = require_text(extension_name, "extension_name")
        with self._lock:
            return tuple(self._by_extension.get(name, ()))

    def list(self) -> tuple[ExtensionTraceEvent, ...]:
        with self._lock:
            return tuple(self._events)
