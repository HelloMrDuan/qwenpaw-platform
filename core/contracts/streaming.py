"""Ordered streaming event contracts and pure sequence validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping


STREAM_SCHEMA_VERSION = "stream.v1"


class StreamEventType(str, Enum):
    """Events supported by the first stream contract version."""

    AGENT_START = "agent.start"
    AGENT_THINKING = "agent.thinking"
    MESSAGE_DELTA = "message.delta"
    TOOL_START = "tool.start"
    TOOL_PROGRESS = "tool.progress"
    TOOL_RESULT = "tool.result"
    FILE_CREATED = "file.created"
    AGENT_DONE = "agent.done"
    TOOL_ERROR = "tool.error"
    AGENT_ERROR = "agent.error"
    AGENT_CANCELLED = "agent.cancelled"


AGENT_TERMINAL_EVENTS = frozenset(
    {
        StreamEventType.AGENT_DONE,
        StreamEventType.AGENT_ERROR,
        StreamEventType.AGENT_CANCELLED,
    }
)
TOOL_TERMINAL_EVENTS = frozenset(
    {StreamEventType.TOOL_RESULT, StreamEventType.TOOL_ERROR}
)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_utc_timestamp(value: str) -> None:
    _require_text(value, "timestamp")
    if not value.endswith("Z"):
        raise ValueError("timestamp must be an RFC 3339 UTC value ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp must be a valid RFC 3339 UTC value") from exc


@dataclass(frozen=True, slots=True)
class StreamSource:
    """Component that emitted an event."""

    type: str
    name: str

    def __post_init__(self) -> None:
        _require_text(self.type, "source.type")
        _require_text(self.name, "source.name")

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StreamSource":
        if not isinstance(data, Mapping):
            raise TypeError("source must be a mapping")
        return cls(type=data["type"], name=data["name"])


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """A single ordered response event.

    The model is transport-neutral and does not publish events by itself.
    ``version`` is serialized as ``schema_version``.
    """

    version: str
    event_id: str
    event: StreamEventType
    stream_id: str
    sequence: int
    timestamp: str
    trace_id: str
    session_id: str
    conversation_id: str
    task_id: str
    source: StreamSource
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "version",
            "event_id",
            "stream_id",
            "trace_id",
            "session_id",
            "conversation_id",
            "task_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        if self.version != STREAM_SCHEMA_VERSION:
            raise ValueError(f"unsupported stream version: {self.version}")
        if isinstance(self.event, str):
            try:
                object.__setattr__(self, "event", StreamEventType(self.event))
            except ValueError as exc:
                raise ValueError(f"unsupported stream event: {self.event}") from exc
        elif not isinstance(self.event, StreamEventType):
            raise TypeError("event must be a StreamEventType or supported string")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise TypeError("sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("sequence must be greater than or equal to 1")
        _validate_utc_timestamp(self.timestamp)
        if not isinstance(self.source, StreamSource):
            raise TypeError("source must be a StreamSource")
        if not isinstance(self.payload, Mapping):
            raise TypeError("payload must be a mapping")
        self._validate_payload()

    @property
    def schema_version(self) -> str:
        return self.version

    @property
    def is_terminal(self) -> bool:
        return self.event in AGENT_TERMINAL_EVENTS

    def _validate_payload(self) -> None:
        if self.event is StreamEventType.MESSAGE_DELTA:
            delta = self.payload.get("delta")
            if not isinstance(delta, str):
                raise ValueError("message.delta requires a string payload.delta")
        if self.event in {
            StreamEventType.TOOL_START,
            StreamEventType.TOOL_PROGRESS,
            StreamEventType.TOOL_RESULT,
            StreamEventType.TOOL_ERROR,
        }:
            _require_text(self.payload.get("tool_call_id"), "payload.tool_call_id")
            _require_text(self.payload.get("tool"), "payload.tool")
        if self.event is StreamEventType.TOOL_PROGRESS:
            progress = self.payload.get("progress")
            if not isinstance(progress, Mapping):
                raise ValueError("tool.progress requires a mapping payload.progress")
            percent = progress.get("percent")
            if percent is not None:
                if not isinstance(percent, (int, float)) or isinstance(percent, bool):
                    raise TypeError("payload.progress.percent must be numeric")
                if not 0 <= percent <= 100:
                    raise ValueError("payload.progress.percent must be between 0 and 100")
        if self.event is StreamEventType.TOOL_RESULT:
            _require_text(self.payload.get("status"), "payload.status")
        if self.event is StreamEventType.TOOL_ERROR:
            error = self.payload.get("error")
            if not isinstance(error, Mapping):
                raise ValueError("tool.error requires a mapping payload.error")
            _require_text(error.get("code"), "payload.error.code")
        if self.event is StreamEventType.FILE_CREATED:
            artifact = self.payload.get("artifact")
            if not isinstance(artifact, Mapping):
                raise ValueError("file.created requires a mapping payload.artifact")
            _require_text(artifact.get("id"), "payload.artifact.id")
            tool_call_id = self.payload.get("tool_call_id")
            if tool_call_id is not None:
                _require_text(tool_call_id, "payload.tool_call_id")
        if self.event is StreamEventType.AGENT_START:
            _require_text(self.payload.get("agent_id"), "payload.agent_id")
        if self.event is StreamEventType.AGENT_DONE:
            final = self.payload.get("final")
            if not isinstance(final, str):
                raise ValueError("agent.done requires a string payload.final")
        if self.event is StreamEventType.AGENT_ERROR:
            error = self.payload.get("error")
            if not isinstance(error, Mapping):
                raise ValueError("agent.error requires a mapping payload.error")
            _require_text(error.get("code"), "payload.error.code")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable wire representation."""

        return {
            "schema_version": self.version,
            "event_id": self.event_id,
            "event": self.event.value,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "task_id": self.task_id,
            "source": self.source.to_dict(),
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StreamEvent":
        """Build and validate a StreamEvent from decoded JSON."""

        if not isinstance(data, Mapping):
            raise TypeError("stream event data must be a mapping")
        version = data.get("schema_version", data.get("version"))
        if "schema_version" in data and "version" in data:
            if data["schema_version"] != data["version"]:
                raise ValueError("schema_version and version must match")
        return cls(
            version=version,
            event_id=data["event_id"],
            event=data["event"],
            stream_id=data["stream_id"],
            sequence=data["sequence"],
            timestamp=data["timestamp"],
            trace_id=data["trace_id"],
            session_id=data["session_id"],
            conversation_id=data["conversation_id"],
            task_id=data["task_id"],
            source=StreamSource.from_dict(data["source"]),
            payload=data.get("payload", {}),
        )


class StreamSequenceError(ValueError):
    """Raised when an event collection violates stream ordering rules."""


def validate_stream_sequence(
    events: Iterable[StreamEvent], *, require_terminal: bool = True
) -> None:
    """Validate one stream without publishing, buffering, or executing it.

    The validator enforces ordering, correlation, one Agent lifecycle, and Tool
    start/terminal relationships. It is intentionally a pure contract helper,
    not a runtime event bus.
    """

    sequence = tuple(events)
    if not sequence:
        raise StreamSequenceError("stream must contain at least one event")
    if not all(isinstance(item, StreamEvent) for item in sequence):
        raise TypeError("events must contain only StreamEvent objects")

    first = sequence[0]
    if first.event is not StreamEventType.AGENT_START:
        raise StreamSequenceError("the first event must be agent.start")

    stream_key = (
        first.stream_id,
        first.trace_id,
        first.session_id,
        first.conversation_id,
        first.task_id,
    )
    last_number = 0
    agent_start_count = 0
    terminal_seen = False
    event_ids: set[str] = set()
    active_tools: set[str] = set()
    completed_tools: set[str] = set()
    tool_progress: dict[str, float] = {}

    for item in sequence:
        item_key = (
            item.stream_id,
            item.trace_id,
            item.session_id,
            item.conversation_id,
            item.task_id,
        )
        if item_key != stream_key:
            raise StreamSequenceError("all events must belong to the same stream and task")
        if item.sequence <= last_number:
            raise StreamSequenceError("event sequence numbers must be strictly increasing")
        last_number = item.sequence
        if item.event_id in event_ids:
            raise StreamSequenceError("event_id values must be unique within a stream")
        event_ids.add(item.event_id)
        if terminal_seen:
            raise StreamSequenceError("events cannot appear after an Agent terminal event")

        if item.event is StreamEventType.AGENT_START:
            agent_start_count += 1
            if agent_start_count > 1:
                raise StreamSequenceError("a stream can contain only one agent.start")

        tool_call_id = item.payload.get("tool_call_id")
        if item.event is StreamEventType.TOOL_START:
            if tool_call_id in active_tools or tool_call_id in completed_tools:
                raise StreamSequenceError("tool_call_id cannot be started more than once")
            active_tools.add(tool_call_id)
            tool_progress[tool_call_id] = 0
        elif item.event in {
            StreamEventType.TOOL_PROGRESS,
            StreamEventType.TOOL_RESULT,
            StreamEventType.TOOL_ERROR,
        }:
            if tool_call_id not in active_tools:
                raise StreamSequenceError(
                    f"{item.event.value} requires a preceding tool.start"
                )
            if item.event is StreamEventType.TOOL_PROGRESS:
                percent = item.payload["progress"].get("percent")
                if percent is not None:
                    if percent < tool_progress[tool_call_id]:
                        raise StreamSequenceError("tool progress percent cannot decrease")
                    tool_progress[tool_call_id] = percent
            if item.event in TOOL_TERMINAL_EVENTS:
                active_tools.remove(tool_call_id)
                completed_tools.add(tool_call_id)
                tool_progress.pop(tool_call_id, None)
        elif item.event is StreamEventType.FILE_CREATED and tool_call_id is not None:
            if tool_call_id not in active_tools:
                raise StreamSequenceError(
                    "file.created with tool_call_id requires an active tool call"
                )

        if item.event in AGENT_TERMINAL_EVENTS:
            if active_tools:
                raise StreamSequenceError("Agent cannot terminate with active tool calls")
            terminal_seen = True

    if require_terminal and not terminal_seen:
        raise StreamSequenceError("stream requires an Agent terminal event")
