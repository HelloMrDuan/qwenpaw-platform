"""Models for the local Skill Extension execution boundary."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

from core.contracts import Artifact, SkillResult, StreamEvent
from core.extensions import ExtensionRuntime, ExtensionType


ArtifactResolver = Callable[[Artifact], str | Path]
ArtifactPublisher = Callable[[Path], Artifact]


@runtime_checkable
class StreamEventPublisher(Protocol):
    """Minimal publishing surface accepted from the Extension Streaming Bridge."""

    def publish(self, event: StreamEvent) -> None:
        """Publish one validated event synchronously."""
        ...


@dataclass(frozen=True, slots=True)
class SkillExecutorDescriptor:
    """Resolved and allowlisted Skill executor declaration."""

    name: str
    version: str
    type: ExtensionType
    runtime: ExtensionRuntime
    manifest_path: Path
    executor_path: Path
    callable_name: str
    declared_events: tuple[str, ...]
    artifact_contract: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.type is not ExtensionType.SKILL:
            raise ValueError("executor descriptor requires type=skill")
        if self.runtime is not ExtensionRuntime.PYTHON:
            raise ValueError("the local Skill executor bridge only supports Python")
        if not self.manifest_path.is_file():
            raise ValueError(f"Skill manifest not found: {self.manifest_path}")
        if not self.executor_path.is_file():
            raise ValueError(f"Skill executor not found: {self.executor_path}")
        if not self.callable_name:
            raise ValueError("callable_name must not be empty")
        if not self.declared_events:
            raise ValueError("declared_events must not be empty")
        if not isinstance(self.artifact_contract, Mapping):
            raise TypeError("artifact_contract must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.type.value,
            "runtime": self.runtime.value,
            "manifest_path": str(self.manifest_path),
            "executor_path": str(self.executor_path),
            "callable": self.callable_name,
            "declared_events": list(self.declared_events),
            "artifact_contract": dict(self.artifact_contract),
        }


@dataclass(frozen=True, slots=True)
class SkillRuntimeResult:
    """Validated SkillResult plus the executor identity used to produce it."""

    descriptor: SkillExecutorDescriptor
    result: SkillResult
    published_event_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, SkillExecutorDescriptor):
            raise TypeError("descriptor must be a SkillExecutorDescriptor")
        if not isinstance(self.result, SkillResult):
            raise TypeError("result must be a SkillResult")
        if (
            type(self.published_event_count) is not int
            or self.published_event_count < 0
            or self.published_event_count > len(self.result.events)
        ):
            raise ValueError("published_event_count is invalid")

    @property
    def artifacts(self) -> tuple[Artifact, ...]:
        return tuple(self.result.artifacts)

    @property
    def events(self) -> tuple[StreamEvent, ...]:
        return tuple(self.result.events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor": self.descriptor.to_dict(),
            "result": self.result.to_dict(),
            "published_event_count": self.published_event_count,
        }
