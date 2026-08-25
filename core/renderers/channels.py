"""Offline reference strategies for Console, Telegram, WeCom and WeChat."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.contracts import RenderedOutput, RenderedOutputType, StreamEvent, StreamEventType

from .base import BaseStreamRenderer


def _status_text(event: StreamEvent) -> str | None:
    if event.event is StreamEventType.AGENT_START:
        return "任务已开始"
    if event.event is StreamEventType.AGENT_THINKING:
        value = event.payload.get("safe_summary") or event.payload.get("status")
        return str(value) if value else None
    if event.event is StreamEventType.TOOL_START:
        return f"开始执行 {event.payload.get('tool', 'tool')}"
    if event.event is StreamEventType.TOOL_PROGRESS:
        if event.payload.get("message"):
            return str(event.payload["message"])
        percent = event.payload.get("progress", {}).get("percent")
        return f"{event.payload.get('tool', 'tool')}：{percent}%" if percent is not None else None
    if event.event is StreamEventType.TOOL_RESULT:
        return str(event.payload.get("summary") or "工具执行完成")
    return None


class ConsoleRenderer(BaseStreamRenderer):
    """Render user-visible deltas and safe status events immediately."""

    channel_type = "console"

    def __init__(self) -> None:
        super().__init__()
        self._delta_streams: set[str] = set()

    def _render_event(self, event: StreamEvent) -> tuple[RenderedOutput, ...]:
        if event.event is StreamEventType.MESSAGE_DELTA:
            self._delta_streams.add(event.stream_id)
            return (
                self._make_output(
                    (event,),
                    RenderedOutputType.TEXT_DELTA,
                    text=str(event.payload["delta"]),
                ),
            )
        if event.event is StreamEventType.FILE_CREATED:
            return (self._file_output(event, delivery_mode="artifact_reference"),)
        if event.event in {StreamEventType.TOOL_ERROR, StreamEventType.AGENT_ERROR}:
            return (self._error_output(event),)
        if event.event is StreamEventType.AGENT_DONE:
            if event.stream_id in self._delta_streams:
                return ()
            return (
                self._make_output(
                    (event,),
                    RenderedOutputType.MESSAGE,
                    text=str(event.payload["final"]),
                    final=True,
                ),
            )
        status = _status_text(event)
        if status:
            return (
                self._make_output(
                    (event,), RenderedOutputType.STATUS, text=status
                ),
            )
        return ()


@dataclass(slots=True)
class _AggregateState:
    text: str = ""
    last_emitted: str = ""
    sources: list[StreamEvent] = field(default_factory=list)
    last_event: StreamEvent | None = None


class TelegramRenderer(BaseStreamRenderer):
    """Aggregate deltas and model throttled message create/update actions."""

    channel_type = "telegram"

    def __init__(self, *, min_update_chars: int = 80) -> None:
        if not isinstance(min_update_chars, int) or isinstance(min_update_chars, bool):
            raise TypeError("min_update_chars must be an integer")
        if min_update_chars < 1:
            raise ValueError("min_update_chars must be greater than zero")
        super().__init__()
        self.min_update_chars = min_update_chars
        self._buffers: dict[str, _AggregateState] = {}

    def _state(self, event: StreamEvent) -> _AggregateState:
        state = self._buffers.setdefault(event.stream_id, _AggregateState())
        state.last_event = event
        return state

    def _emit_state(
        self, state: _AggregateState, *, final: bool = False
    ) -> tuple[RenderedOutput, ...]:
        if state.text == state.last_emitted or state.last_event is None:
            return ()
        sources = tuple(state.sources) or (state.last_event,)
        output_type = (
            RenderedOutputType.MESSAGE
            if not state.last_emitted
            else RenderedOutputType.MESSAGE_UPDATE
        )
        output = self._make_output(
            sources,
            output_type,
            text=state.text,
            final=final,
            metadata={
                "delivery_mode": "throttled_edit",
                "min_update_chars": self.min_update_chars,
            },
        )
        state.last_emitted = state.text
        state.sources.clear()
        return (output,)

    def _render_event(self, event: StreamEvent) -> tuple[RenderedOutput, ...]:
        if event.event is StreamEventType.MESSAGE_DELTA:
            state = self._state(event)
            state.text += str(event.payload["delta"])
            state.sources.append(event)
            if len(state.text) - len(state.last_emitted) >= self.min_update_chars:
                return self._emit_state(state)
            return ()
        if event.event is StreamEventType.AGENT_DONE:
            state = self._state(event)
            state.text = str(event.payload["final"])
            state.sources.append(event)
            return self._emit_state(state, final=True)
        if event.event is StreamEventType.FILE_CREATED:
            return (self._file_output(event, delivery_mode="attachment_or_link"),)
        if event.event in {StreamEventType.TOOL_ERROR, StreamEventType.AGENT_ERROR}:
            state = self._state(event)
            return (*self._emit_state(state), self._error_output(event))
        return ()

    def _flush_buffer(self) -> tuple[RenderedOutput, ...]:
        outputs: list[RenderedOutput] = []
        for state in self._buffers.values():
            outputs.extend(self._emit_state(state))
        return tuple(outputs)


@dataclass(slots=True)
class _SegmentState:
    pending: str = ""
    sources: list[StreamEvent] = field(default_factory=list)
    last_event: StreamEvent | None = None
    received_delta: bool = False


class WeComRenderer(BaseStreamRenderer):
    """Convert deltas into bounded text segments and explicit file actions."""

    channel_type = "wecom"

    def __init__(self, *, segment_chars: int = 1000) -> None:
        if not isinstance(segment_chars, int) or isinstance(segment_chars, bool):
            raise TypeError("segment_chars must be an integer")
        if segment_chars < 1:
            raise ValueError("segment_chars must be greater than zero")
        super().__init__()
        self.segment_chars = segment_chars
        self._buffers: dict[str, _SegmentState] = {}

    def _state(self, event: StreamEvent) -> _SegmentState:
        state = self._buffers.setdefault(event.stream_id, _SegmentState())
        state.last_event = event
        return state

    def _drain(
        self,
        state: _SegmentState,
        *,
        include_remainder: bool,
        final: bool = False,
    ) -> tuple[RenderedOutput, ...]:
        if state.last_event is None:
            return ()
        chunks: list[tuple[str, tuple[StreamEvent, ...]]] = []
        while len(state.pending) >= self.segment_chars:
            chunk = state.pending[: self.segment_chars]
            state.pending = state.pending[self.segment_chars :]
            sources = tuple(state.sources) or (state.last_event,)
            state.sources.clear()
            chunks.append((chunk, sources))
        if include_remainder and state.pending:
            sources = tuple(state.sources) or (state.last_event,)
            chunks.append((state.pending, sources))
            state.pending = ""
            state.sources.clear()
        return tuple(
            self._make_output(
                sources,
                RenderedOutputType.MESSAGE,
                text=chunk,
                final=final and index == len(chunks) - 1,
                metadata={
                    "delivery_mode": "segment",
                    "segment_limit": self.segment_chars,
                },
            )
            for index, (chunk, sources) in enumerate(chunks)
        )

    def _render_event(self, event: StreamEvent) -> tuple[RenderedOutput, ...]:
        if event.event is StreamEventType.MESSAGE_DELTA:
            state = self._state(event)
            state.received_delta = True
            state.pending += str(event.payload["delta"])
            state.sources.append(event)
            return self._drain(state, include_remainder=False)
        if event.event is StreamEventType.AGENT_DONE:
            state = self._state(event)
            if not state.received_delta:
                state.pending = str(event.payload["final"])
            state.sources.append(event)
            return self._drain(state, include_remainder=True, final=True)
        if event.event is StreamEventType.FILE_CREATED:
            return (self._file_output(event, delivery_mode="file_message"),)
        if event.event in {StreamEventType.TOOL_ERROR, StreamEventType.AGENT_ERROR}:
            state = self._state(event)
            return (
                *self._drain(state, include_remainder=True),
                self._error_output(event),
            )
        return ()

    def _flush_buffer(self) -> tuple[RenderedOutput, ...]:
        outputs: list[RenderedOutput] = []
        for state in self._buffers.values():
            outputs.extend(self._drain(state, include_remainder=True))
        return tuple(outputs)


class WeChatRenderer(BaseStreamRenderer):
    """Buffer deltas until flush or terminal events; never assumes editing."""

    channel_type = "wechat"

    def __init__(self) -> None:
        super().__init__()
        self._buffers: dict[str, _SegmentState] = {}

    def _state(self, event: StreamEvent) -> _SegmentState:
        state = self._buffers.setdefault(event.stream_id, _SegmentState())
        state.last_event = event
        return state

    def _emit(
        self, state: _SegmentState, *, final: bool = False
    ) -> tuple[RenderedOutput, ...]:
        if not state.pending or state.last_event is None:
            return ()
        sources = tuple(state.sources) or (state.last_event,)
        output = self._make_output(
            sources,
            RenderedOutputType.MESSAGE,
            text=state.pending,
            final=final,
            metadata={"delivery_mode": "buffered_reply"},
        )
        state.pending = ""
        state.sources.clear()
        return (output,)

    def _render_event(self, event: StreamEvent) -> tuple[RenderedOutput, ...]:
        if event.event is StreamEventType.MESSAGE_DELTA:
            state = self._state(event)
            state.received_delta = True
            state.pending += str(event.payload["delta"])
            state.sources.append(event)
            return ()
        if event.event is StreamEventType.AGENT_DONE:
            state = self._state(event)
            if not state.received_delta:
                state.pending = str(event.payload["final"])
            state.sources.append(event)
            return self._emit(state, final=True)
        if event.event is StreamEventType.FILE_CREATED:
            return (self._file_output(event, delivery_mode="download_link"),)
        if event.event in {StreamEventType.TOOL_ERROR, StreamEventType.AGENT_ERROR}:
            state = self._state(event)
            return (*self._emit(state), self._error_output(event))
        return ()

    def _flush_buffer(self) -> tuple[RenderedOutput, ...]:
        outputs: list[RenderedOutput] = []
        for state in self._buffers.values():
            outputs.extend(self._emit(state))
        return tuple(outputs)
