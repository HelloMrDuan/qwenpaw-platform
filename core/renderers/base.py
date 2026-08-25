"""Shared mechanics for transport-neutral reference Stream Renderers."""

from __future__ import annotations

from collections.abc import Sequence

from core.contracts import (
    Artifact,
    RENDER_OUTPUT_SCHEMA_VERSION,
    RenderedOutput,
    RenderedOutputType,
    StreamEvent,
)


class RenderError(ValueError):
    """Base error raised by Extension reference Renderers."""


class RenderOrderError(RenderError):
    """Raised when events reach a Renderer out of order or with new identity."""


class RendererClosedError(RenderError):
    """Raised when a closed Renderer is used again."""


class BaseStreamRenderer:
    """Validate ordering and build Channel-neutral outputs.

    The Streaming Bridge remains the authoritative lifecycle validator. This
    local guard prevents a Renderer used on its own from displaying duplicate,
    reordered or cross-session events.
    """

    channel_type = "base"

    def __init__(self) -> None:
        self._closed = False
        self._last_sequences: dict[str, int] = {}
        self._correlations: dict[str, tuple[str, str, str, str]] = {}
        self._event_ids: set[str] = set()
        self._output_counter = 0

    def render(self, event: StreamEvent) -> tuple[RenderedOutput, ...]:
        self._ensure_open()
        self._validate_event(event)
        outputs = self._validate_outputs(self._render_event(event))
        self._last_sequences[event.stream_id] = event.sequence
        self._correlations[event.stream_id] = (
            event.trace_id,
            event.session_id,
            event.conversation_id,
            event.task_id,
        )
        self._event_ids.add(event.event_id)
        return outputs

    def flush(self) -> tuple[RenderedOutput, ...]:
        self._ensure_open()
        return self._validate_outputs(self._flush_buffer())

    def close(self) -> tuple[RenderedOutput, ...]:
        if self._closed:
            return ()
        outputs = self._validate_outputs(self._flush_buffer())
        self._closed = True
        return outputs

    def _ensure_open(self) -> None:
        if self._closed:
            raise RendererClosedError("renderer is closed")

    def _validate_event(self, event: StreamEvent) -> None:
        if not isinstance(event, StreamEvent):
            raise TypeError("event must be a StreamEvent")
        if event.event_id in self._event_ids:
            raise RenderOrderError("event_id must be unique within a Renderer")
        previous = self._last_sequences.get(event.stream_id, 0)
        if event.sequence <= previous:
            raise RenderOrderError("event sequence must be strictly increasing")
        correlation = (
            event.trace_id,
            event.session_id,
            event.conversation_id,
            event.task_id,
        )
        expected = self._correlations.get(event.stream_id)
        if expected is not None and correlation != expected:
            raise RenderOrderError("stream correlation fields cannot change")

    def _validate_outputs(
        self, outputs: Sequence[RenderedOutput]
    ) -> tuple[RenderedOutput, ...]:
        if isinstance(outputs, (str, bytes)):
            raise TypeError("renderer outputs must be a sequence")
        normalized = tuple(outputs)
        if not all(isinstance(item, RenderedOutput) for item in normalized):
            raise TypeError("renderer outputs must contain only RenderedOutput")
        if any(item.channel != self.channel_type for item in normalized):
            raise RenderError("rendered output channel does not match Renderer")
        return normalized

    def _make_output(
        self,
        events: Sequence[StreamEvent],
        output_type: RenderedOutputType,
        *,
        text: str | None = None,
        artifact: Artifact | None = None,
        final: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> RenderedOutput:
        source_events = tuple(events)
        if not source_events:
            raise RenderError("an output requires at least one source event")
        first = source_events[0]
        if any(
            item.stream_id != first.stream_id or item.session_id != first.session_id
            for item in source_events
        ):
            raise RenderError("one output cannot combine streams or sessions")
        self._output_counter += 1
        return RenderedOutput(
            id=f"rnd_{self.channel_type}_{self._output_counter:06d}",
            version=RENDER_OUTPUT_SCHEMA_VERSION,
            type=output_type,
            channel=self.channel_type,
            session_id=first.session_id,
            stream_id=first.stream_id,
            sequence=max(item.sequence for item in source_events),
            source_event_ids=tuple(item.event_id for item in source_events),
            text=text,
            artifact=artifact,
            final=final,
            metadata=metadata or {},
        )

    def _artifact_from_event(self, event: StreamEvent) -> Artifact:
        data = event.payload.get("artifact")
        try:
            return Artifact.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderError("file.created requires a complete Artifact") from exc

    def _file_output(
        self, event: StreamEvent, *, delivery_mode: str
    ) -> RenderedOutput:
        artifact = self._artifact_from_event(event)
        return self._make_output(
            (event,),
            RenderedOutputType.FILE,
            text=artifact.name,
            artifact=artifact,
            metadata={
                "artifact_delivery": delivery_mode,
                "artifact_uri": artifact.uri,
            },
        )

    def _error_output(self, event: StreamEvent) -> RenderedOutput:
        error = event.payload.get("error", {})
        message = error.get("message") or error.get("code") or "执行失败"
        return self._make_output(
            (event,),
            RenderedOutputType.ERROR,
            text=str(message),
            final=event.event.value.startswith("agent."),
            metadata={"error_code": str(error.get("code") or "UNKNOWN")},
        )

    def _render_event(self, event: StreamEvent) -> Sequence[RenderedOutput]:
        raise NotImplementedError

    def _flush_buffer(self) -> Sequence[RenderedOutput]:
        return ()
