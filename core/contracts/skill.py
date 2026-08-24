"""Data contracts for invoking workspace skills through an extension boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .artifact import Artifact
from .streaming import StreamEvent


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    """Discoverable metadata for a versioned Skill extension."""

    id: str
    name: str
    version: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("id", "name", "version", "description"):
            _require_text(getattr(self, field_name), field_name)
        for field_name in ("input_schema", "output_schema", "metadata"):
            if not isinstance(getattr(self, field_name), Mapping):
                raise TypeError(f"{field_name} must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillMetadata":
        if not isinstance(data, Mapping):
            raise TypeError("skill metadata must be a mapping")
        return cls(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            description=data["description"],
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class SkillRequest:
    """Transport-neutral input passed to a future Skill executor adapter."""

    request_id: str
    skill_id: str
    files: Sequence[Artifact] = field(default_factory=tuple)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.skill_id, "skill_id")
        if isinstance(self.files, (str, bytes)):
            raise TypeError("files must be a sequence of Artifact objects")
        normalized_files = tuple(self.files)
        if not all(isinstance(item, Artifact) for item in normalized_files):
            raise TypeError("files must contain only Artifact objects")
        object.__setattr__(self, "files", normalized_files)
        if not isinstance(self.parameters, Mapping):
            raise TypeError("parameters must be a mapping")
        if not isinstance(self.context, Mapping):
            raise TypeError("context must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "files": [item.to_dict() for item in self.files],
            "parameters": dict(self.parameters),
            "context": dict(self.context),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillRequest":
        if not isinstance(data, Mapping):
            raise TypeError("skill request must be a mapping")
        return cls(
            request_id=data["request_id"],
            skill_id=data["skill_id"],
            files=tuple(Artifact.from_dict(item) for item in data.get("files", [])),
            parameters=data.get("parameters", {}),
            context=data.get("context", {}),
        )


@dataclass(frozen=True, slots=True)
class SkillResult:
    """Normalized Skill output returned to the Tool/Streaming boundary."""

    request_id: str
    success: bool
    message: str
    artifacts: Sequence[Artifact] = field(default_factory=tuple)
    events: Sequence[StreamEvent] = field(default_factory=tuple)
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        if not isinstance(self.success, bool):
            raise TypeError("success must be a boolean")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        if isinstance(self.artifacts, (str, bytes)):
            raise TypeError("artifacts must be a sequence of Artifact objects")
        normalized_artifacts = tuple(self.artifacts)
        if not all(isinstance(item, Artifact) for item in normalized_artifacts):
            raise TypeError("artifacts must contain only Artifact objects")
        object.__setattr__(self, "artifacts", normalized_artifacts)
        if isinstance(self.events, (str, bytes)):
            raise TypeError("events must be a sequence of StreamEvent objects")
        normalized_events = tuple(self.events)
        if not all(isinstance(item, StreamEvent) for item in normalized_events):
            raise TypeError("events must contain only StreamEvent objects")
        object.__setattr__(self, "events", normalized_events)
        if self.error is not None and not isinstance(self.error, Mapping):
            raise TypeError("error must be a mapping or None")
        if self.success and self.error is not None:
            raise ValueError("successful results cannot contain an error")
        if not self.success and self.error is None:
            raise ValueError("failed results require an error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "message": self.message,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "events": [item.to_dict() for item in self.events],
            "error": dict(self.error) if self.error is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillResult":
        if not isinstance(data, Mapping):
            raise TypeError("skill result must be a mapping")
        return cls(
            request_id=data["request_id"],
            success=data["success"],
            message=data.get("message", ""),
            artifacts=tuple(
                Artifact.from_dict(item) for item in data.get("artifacts", [])
            ),
            events=tuple(StreamEvent.from_dict(item) for item in data.get("events", [])),
            error=data.get("error"),
        )
