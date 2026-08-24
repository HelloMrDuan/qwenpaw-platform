"""In-memory replay store with incremental stream validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from core.contracts import (
    AGENT_TERMINAL_EVENTS,
    StreamEvent,
    StreamEventType,
    StreamSequenceError,
)


@dataclass(slots=True)
class _StreamState:
    correlation: tuple[str, str, str, str]
    last_sequence: int = 0
    agent_started: bool = False
    agent_terminal: bool = False
    active_tools: set[str] = field(default_factory=set)
    completed_tools: set[str] = field(default_factory=set)
    tool_progress: dict[str, float] = field(default_factory=dict)


class StreamReplay:
    """Store events by session and reject invalid incremental publication.

    Unlike ``validate_stream_sequence``, this store also accepts Skill-only
    streams whose first event is ``tool.start`` and which have no Agent
    terminal event. This matches Extension executors such as PDF Editor.
    """

    def __init__(self) -> None:
        self._events_by_session: dict[str, list[StreamEvent]] = {}
        self._streams: dict[str, _StreamState] = {}
        self._event_ids: set[str] = set()
        self._lock = RLock()

    def append(self, event: StreamEvent) -> None:
        if not isinstance(event, StreamEvent):
            raise TypeError("event must be a StreamEvent")
        with self._lock:
            self._validate_and_advance(event)
            self._event_ids.add(event.event_id)
            self._events_by_session.setdefault(event.session_id, []).append(event)

    def replay(self, session_id: str) -> tuple[StreamEvent, ...]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            return tuple(self._events_by_session.get(session_id, ()))

    def _validate_and_advance(self, event: StreamEvent) -> None:
        if event.event_id in self._event_ids:
            raise StreamSequenceError("event_id values must be unique in the bridge")

        correlation = (
            event.trace_id,
            event.session_id,
            event.conversation_id,
            event.task_id,
        )
        state = self._streams.get(event.stream_id)
        if state is None:
            if event.event not in {
                StreamEventType.AGENT_START,
                StreamEventType.TOOL_START,
            }:
                raise StreamSequenceError(
                    "the first bridge event must be agent.start or tool.start"
                )
            state = _StreamState(correlation=correlation)
        elif state.correlation != correlation:
            raise StreamSequenceError(
                "stream correlation and session fields cannot change"
            )

        if event.sequence <= state.last_sequence:
            raise StreamSequenceError(
                "event sequence numbers must be strictly increasing"
            )
        if state.agent_terminal:
            raise StreamSequenceError(
                "events cannot appear after an Agent terminal event"
            )

        active_tools = set(state.active_tools)
        completed_tools = set(state.completed_tools)
        tool_progress = dict(state.tool_progress)
        agent_started = state.agent_started
        agent_terminal = state.agent_terminal

        if event.event is StreamEventType.AGENT_START:
            if state.last_sequence != 0 or agent_started:
                raise StreamSequenceError(
                    "agent.start must be the first event and occur only once"
                )
            agent_started = True

        tool_call_id = event.payload.get("tool_call_id")
        if event.event is StreamEventType.TOOL_START:
            if tool_call_id in active_tools or tool_call_id in completed_tools:
                raise StreamSequenceError("tool_call_id cannot be started more than once")
            active_tools.add(tool_call_id)
            tool_progress[tool_call_id] = 0.0
        elif event.event in {
            StreamEventType.TOOL_PROGRESS,
            StreamEventType.TOOL_RESULT,
            StreamEventType.TOOL_ERROR,
        }:
            if tool_call_id not in active_tools:
                raise StreamSequenceError(
                    f"{event.event.value} requires a preceding tool.start"
                )
            if event.event is StreamEventType.TOOL_PROGRESS:
                percent = event.payload["progress"].get("percent")
                if percent is not None:
                    if percent < tool_progress[tool_call_id]:
                        raise StreamSequenceError(
                            "tool progress percent cannot decrease"
                        )
                    tool_progress[tool_call_id] = float(percent)
            else:
                active_tools.remove(tool_call_id)
                completed_tools.add(tool_call_id)
                tool_progress.pop(tool_call_id, None)
        elif event.event is StreamEventType.FILE_CREATED and tool_call_id is not None:
            if tool_call_id not in active_tools:
                raise StreamSequenceError(
                    "file.created with tool_call_id requires an active tool call"
                )

        if event.event in AGENT_TERMINAL_EVENTS:
            if active_tools:
                raise StreamSequenceError(
                    "Agent cannot terminate with active tool calls"
                )
            agent_terminal = True

        state.last_sequence = event.sequence
        state.agent_started = agent_started
        state.agent_terminal = agent_terminal
        state.active_tools = active_tools
        state.completed_tools = completed_tools
        state.tool_progress = tool_progress
        self._streams[event.stream_id] = state
