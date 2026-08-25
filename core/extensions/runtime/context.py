"""Correlation context shared by one Extension Runtime Gateway operation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Sequence

from core.contracts import Artifact, StreamEvent


EXTENSION_RUNTIME_CONTEXT_VERSION = "qwenpaw-extension-runtime-context.v1"


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class ExtensionRuntimeContext:
    """Immutable identity and outputs for one Extension dispatch operation."""

    extension_id: str
    version: str
    trace_id: str
    session_id: str
    artifacts: Sequence[Artifact] = field(default_factory=tuple)
    events: Sequence[StreamEvent] = field(default_factory=tuple)
    schema_version: str = EXTENSION_RUNTIME_CONTEXT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXTENSION_RUNTIME_CONTEXT_VERSION:
            raise ValueError("unsupported Extension Runtime Context version")
        for field_name in ("extension_id", "version", "trace_id", "session_id"):
            object.__setattr__(
                self,
                field_name,
                _require_text(getattr(self, field_name), field_name),
            )

        if isinstance(self.artifacts, (str, bytes)):
            raise TypeError("artifacts must be a sequence of Artifact objects")
        artifacts = tuple(self.artifacts)
        if not all(isinstance(item, Artifact) for item in artifacts):
            raise TypeError("artifacts must contain only Artifact objects")
        if len({item.id for item in artifacts}) != len(artifacts):
            raise ValueError("artifact identifiers must be unique within a context")
        object.__setattr__(self, "artifacts", artifacts)

        if isinstance(self.events, (str, bytes)):
            raise TypeError("events must be a sequence of StreamEvent objects")
        events = tuple(self.events)
        if not all(isinstance(item, StreamEvent) for item in events):
            raise TypeError("events must contain only StreamEvent objects")
        if len({item.event_id for item in events}) != len(events):
            raise ValueError("event identifiers must be unique within a context")
        if any(item.trace_id != self.trace_id for item in events):
            raise ValueError("context events must share the context trace_id")
        if any(item.session_id != self.session_id for item in events):
            raise ValueError("context events must share the context session_id")
        object.__setattr__(self, "events", events)

    def with_outputs(
        self,
        *,
        artifacts: Sequence[Artifact] | None = None,
        events: Sequence[StreamEvent] | None = None,
    ) -> "ExtensionRuntimeContext":
        """Return a validated context containing operation outputs."""

        return replace(
            self,
            artifacts=self.artifacts if artifacts is None else tuple(artifacts),
            events=self.events if events is None else tuple(events),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extension_id": self.extension_id,
            "version": self.version,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "events": [item.to_dict() for item in self.events],
        }
