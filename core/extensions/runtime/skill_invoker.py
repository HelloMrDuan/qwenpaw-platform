"""Validated invocation flow from Extension Registry to SkillResult."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.contracts import (
    Artifact,
    SkillRequest,
    SkillResult,
    StreamEventType,
    StreamSequenceError,
)
from core.extensions import ExtensionRegistry
from core.streaming import StreamReplay

from .executor_bridge import ExtensionExecutorBridge
from .models import (
    ArtifactPublisher,
    ArtifactResolver,
    SkillExecutorDescriptor,
    SkillRuntimeResult,
    StreamEventPublisher,
)


class SkillInvocationError(RuntimeError):
    """Raised when an executor result violates its Extension Manifest contract."""


class SkillInvoker:
    """Invoke an allowlisted Skill and publish only its validated events."""

    def __init__(
        self,
        repository_root: str | Path,
        registry: ExtensionRegistry,
        *,
        executor_bridge: ExtensionExecutorBridge | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.registry = registry
        self.executor_bridge = executor_bridge or ExtensionExecutorBridge(
            self.repository_root, registry
        )

    @classmethod
    def from_repository(cls, repository_root: str | Path) -> "SkillInvoker":
        root = Path(repository_root).resolve()
        registry = ExtensionRegistry(root)
        registry.discover()
        return cls(root, registry)

    def describe(self, skill_id: str) -> SkillExecutorDescriptor:
        return self.executor_bridge.describe(skill_id)

    def invoke(
        self,
        request: SkillRequest,
        *,
        resolve_artifact: ArtifactResolver,
        publish_artifact: ArtifactPublisher,
        event_publisher: StreamEventPublisher | None = None,
        python_executable: str | None = None,
    ) -> SkillRuntimeResult:
        descriptor, result = self.executor_bridge.execute(
            request,
            resolve_artifact=resolve_artifact,
            publish_artifact=publish_artifact,
            python_executable=python_executable,
        )
        self._validate_result(request, descriptor, result)
        published = 0
        if event_publisher is not None:
            if not isinstance(event_publisher, StreamEventPublisher):
                raise TypeError("event_publisher must implement publish(event)")
            for event in result.events:
                event_publisher.publish(event)
                published += 1
        return SkillRuntimeResult(
            descriptor=descriptor,
            result=result,
            published_event_count=published,
        )

    @classmethod
    def _validate_result(
        cls,
        request: SkillRequest,
        descriptor: SkillExecutorDescriptor,
        result: SkillResult,
    ) -> None:
        if result.request_id != request.request_id:
            raise SkillInvocationError("SkillResult request_id does not match SkillRequest")
        events = tuple(result.events)
        if not events:
            raise SkillInvocationError("SkillResult must contain StreamEvent output")
        if [event.sequence for event in events] != list(range(1, len(events) + 1)):
            raise SkillInvocationError("Skill events must use contiguous sequence numbers")
        if len({event.event_id for event in events}) != len(events):
            raise SkillInvocationError("Skill event_id values must be unique")
        correlation = {
            (
                event.stream_id,
                event.trace_id,
                event.session_id,
                event.conversation_id,
                event.task_id,
            )
            for event in events
        }
        if len(correlation) != 1:
            raise SkillInvocationError("Skill events must share one correlation context")
        replay_validator = StreamReplay()
        try:
            for event in events:
                replay_validator.append(event)
        except StreamSequenceError as exc:
            raise SkillInvocationError(f"invalid Skill event order: {exc}") from exc
        declared_events = set(descriptor.declared_events)
        emitted_events = {event.event.value for event in events}
        undeclared = sorted(emitted_events - declared_events)
        if undeclared:
            raise SkillInvocationError(
                f"Skill emitted events not declared by Manifest: {', '.join(undeclared)}"
            )
        if any(event.source.type != "skill" or event.source.name != descriptor.name for event in events):
            raise SkillInvocationError("Skill event source does not match executor identity")
        if events[0].event is not StreamEventType.TOOL_START:
            raise SkillInvocationError("Skill event stream must begin with tool.start")

        if result.success:
            if events[-1].event is not StreamEventType.TOOL_RESULT:
                raise SkillInvocationError("successful Skill stream must end with tool.result")
            if any(event.event is StreamEventType.TOOL_ERROR for event in events):
                raise SkillInvocationError("successful Skill stream cannot contain tool.error")
            cls._validate_artifacts(descriptor.artifact_contract, tuple(result.artifacts))
            created_ids = {
                str(event.payload["artifact"]["id"])
                for event in events
                if event.event is StreamEventType.FILE_CREATED
            }
            result_ids = {artifact.id for artifact in result.artifacts}
            if created_ids != result_ids:
                raise SkillInvocationError(
                    "file.created events must match returned Artifact identifiers"
                )
        elif events[-1].event is not StreamEventType.TOOL_ERROR:
            raise SkillInvocationError("failed Skill stream must end with tool.error")

    @staticmethod
    def _validate_artifacts(
        contract: Mapping[str, Any], artifacts: tuple[Artifact, ...]
    ) -> None:
        outputs = contract.get("outputs")
        if not isinstance(outputs, list):
            raise SkillInvocationError("Skill Manifest artifact outputs are invalid")
        for declaration in outputs:
            if not isinstance(declaration, Mapping) or not declaration.get("required"):
                continue
            kind = declaration.get("kind")
            mime_types = declaration.get("mime_types")
            if not isinstance(mime_types, list):
                raise SkillInvocationError("Skill Manifest mime_types are invalid")
            matched = any(
                artifact.kind.value == kind
                and any(
                    SkillInvoker._mime_matches(artifact.mime_type, pattern)
                    for pattern in mime_types
                )
                for artifact in artifacts
            )
            if not matched:
                raise SkillInvocationError(
                    f"required Artifact output was not returned: {declaration.get('name')}"
                )

    @staticmethod
    def _mime_matches(mime_type: str, pattern: str) -> bool:
        if pattern.endswith("/*"):
            return mime_type.startswith(pattern[:-1])
        return mime_type == pattern
