"""Transport-neutral output and Renderer contracts for StreamEvent consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .artifact import Artifact
from .streaming import StreamEvent


RENDER_OUTPUT_SCHEMA_VERSION = "render.output.v1"


class RenderedOutputType(str, Enum):
    """Channel-neutral presentation actions produced by a Renderer."""

    TEXT_DELTA = "text.delta"
    MESSAGE = "message"
    MESSAGE_UPDATE = "message.update"
    STATUS = "status"
    FILE = "file"
    ERROR = "error"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class RenderedOutput:
    """One proposed Channel presentation action.

    The object is not a delivery receipt and performs no provider I/O. A future
    Channel adapter may turn it into a Console write, message edit, segment,
    attachment upload or download-link message.
    """

    id: str
    version: str
    type: RenderedOutputType
    channel: str
    session_id: str
    stream_id: str
    sequence: int
    source_event_ids: Sequence[str]
    text: str | None = None
    artifact: Artifact | None = None
    final: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("id", "version", "channel", "session_id", "stream_id"):
            _require_text(getattr(self, field_name), field_name)
        if self.version != RENDER_OUTPUT_SCHEMA_VERSION:
            raise ValueError(f"unsupported rendered output version: {self.version}")
        if isinstance(self.type, str):
            try:
                object.__setattr__(self, "type", RenderedOutputType(self.type))
            except ValueError as exc:
                raise ValueError(f"unsupported rendered output type: {self.type}") from exc
        elif not isinstance(self.type, RenderedOutputType):
            raise TypeError("type must be a RenderedOutputType or supported string")
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise TypeError("sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("sequence must be greater than or equal to 1")
        if isinstance(self.source_event_ids, (str, bytes)):
            raise TypeError("source_event_ids must be a sequence of strings")
        source_event_ids = tuple(self.source_event_ids)
        if not source_event_ids:
            raise ValueError("source_event_ids must not be empty")
        for item in source_event_ids:
            _require_text(item, "source_event_ids item")
        object.__setattr__(self, "source_event_ids", source_event_ids)
        if self.text is not None and not isinstance(self.text, str):
            raise TypeError("text must be a string or None")
        if self.artifact is not None and not isinstance(self.artifact, Artifact):
            raise TypeError("artifact must be an Artifact or None")
        if self.type is RenderedOutputType.FILE and self.artifact is None:
            raise ValueError("file output requires an artifact")
        if not isinstance(self.final, bool):
            raise TypeError("final must be a boolean")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")

    @property
    def schema_version(self) -> str:
        return self.version

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.version,
            "id": self.id,
            "type": self.type.value,
            "channel": self.channel,
            "session_id": self.session_id,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "source_event_ids": list(self.source_event_ids),
            "text": self.text,
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "final": self.final,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RenderedOutput":
        if not isinstance(data, Mapping):
            raise TypeError("rendered output data must be a mapping")
        version = data.get("schema_version", data.get("version"))
        if "schema_version" in data and "version" in data:
            if data["schema_version"] != data["version"]:
                raise ValueError("schema_version and version must match")
        artifact = data.get("artifact")
        return cls(
            id=data["id"],
            version=version,
            type=data["type"],
            channel=data["channel"],
            session_id=data["session_id"],
            stream_id=data["stream_id"],
            sequence=data["sequence"],
            source_event_ids=data["source_event_ids"],
            text=data.get("text"),
            artifact=Artifact.from_dict(artifact) if artifact is not None else None,
            final=data.get("final", False),
            metadata=data.get("metadata", {}),
        )


@runtime_checkable
class StreamRenderer(Protocol):
    """Minimum synchronous interface for an Extension-layer Renderer."""

    channel_type: str

    def render(self, event: StreamEvent) -> Sequence[RenderedOutput]:
        """Convert one ordered event into zero or more presentation actions."""
        ...

    def flush(self) -> Sequence[RenderedOutput]:
        """Emit currently buffered presentation actions without closing."""
        ...

    def close(self) -> Sequence[RenderedOutput]:
        """Flush buffered actions and reject future events."""
        ...
