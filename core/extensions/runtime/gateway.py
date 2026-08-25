"""Unified, offline dispatch entrypoint for Extension-layer Runtime bridges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import RLock
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import uuid4

from core.contracts import Artifact, MessageEvent, SkillRequest
from core.extensions import ExtensionMetadata, ExtensionRegistry, ExtensionType
from core.extensions.lifecycle import ExtensionLifecycleManager, HealthReport
from core.extensions.observability import (
    ExtensionHealthStore,
    ExtensionMetricsStore,
    ExtensionTraceStore,
)
from core.streaming import StreamingBridge

from .context import ExtensionRuntimeContext
from .models import ArtifactPublisher, ArtifactResolver, SkillRuntimeResult
from .skill_invoker import SkillInvoker


class ExtensionGatewayOperation(str, Enum):
    INVOKE_SKILL = "skill.invoke"
    INVOKE_PLUGIN = "plugin.invoke"
    RECEIVE_MESSAGE = "adapter.receive"


@dataclass(frozen=True, slots=True)
class ExtensionGatewayResult:
    """One operation result paired with its validated Runtime Context."""

    operation: ExtensionGatewayOperation
    context: ExtensionRuntimeContext
    value: Any

    def __post_init__(self) -> None:
        if isinstance(self.operation, str):
            object.__setattr__(
                self, "operation", ExtensionGatewayOperation(self.operation)
            )
        if not isinstance(self.operation, ExtensionGatewayOperation):
            raise TypeError("operation must be an ExtensionGatewayOperation")
        if not isinstance(self.context, ExtensionRuntimeContext):
            raise TypeError("context must be an ExtensionRuntimeContext")


@runtime_checkable
class PluginInvocationFacade(Protocol):
    """Injected business-neutral call surface for one external Plugin."""

    def invoke(
        self,
        context: ExtensionRuntimeContext,
        payload: Mapping[str, Any],
    ) -> Any:
        ...


@runtime_checkable
class ExtensionMessageReceiver(Protocol):
    """Existing Adapter/Plugin message source exposed to the unified Gateway."""

    def receive_message(self) -> MessageEvent | None:
        ...


class ExtensionRuntimeGatewayError(RuntimeError):
    """Base error for unified Extension dispatch."""


class ExtensionNotAvailableError(ExtensionRuntimeGatewayError):
    """Raised when an Extension is absent, unhealthy, or not registered for an action."""


class ExtensionRuntimeGateway:
    """Coordinate existing Extension bridges without replacing their execution logic."""

    def __init__(
        self,
        registry: ExtensionRegistry,
        lifecycle_manager: ExtensionLifecycleManager,
        *,
        skill_invoker: SkillInvoker,
        streaming_bridge: StreamingBridge,
        health_store: ExtensionHealthStore | None = None,
        metrics_store: ExtensionMetricsStore | None = None,
        trace_store: ExtensionTraceStore | None = None,
        plugin_invokers: Mapping[str, PluginInvocationFacade] | None = None,
        message_receivers: Mapping[str, ExtensionMessageReceiver] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.registry = registry
        self.lifecycle_manager = lifecycle_manager
        self.skill_invoker = skill_invoker
        self.streaming_bridge = streaming_bridge
        self.health_store = health_store or ExtensionHealthStore()
        self.metrics_store = metrics_store or ExtensionMetricsStore()
        self.trace_store = trace_store or ExtensionTraceStore()
        self._plugin_invokers: dict[str, PluginInvocationFacade] = {}
        self._message_receivers: dict[str, ExtensionMessageReceiver] = {}
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._lock = RLock()
        for name, invoker in (plugin_invokers or {}).items():
            self.register_plugin(name, invoker)
        for name, receiver in (message_receivers or {}).items():
            self.register_message_receiver(name, receiver)

    def register_plugin(
        self, extension_id: str, invoker: PluginInvocationFacade
    ) -> None:
        metadata = self._metadata(extension_id, expected=(ExtensionType.PLUGIN,))
        if not isinstance(invoker, PluginInvocationFacade):
            raise TypeError("invoker must implement invoke(context, payload)")
        with self._lock:
            if metadata.name in self._plugin_invokers:
                raise ExtensionRuntimeGatewayError(
                    f"Plugin invocation facade already registered: {metadata.name}"
                )
            self._plugin_invokers[metadata.name] = invoker

    def register_message_receiver(
        self, extension_id: str, receiver: ExtensionMessageReceiver
    ) -> None:
        metadata = self._metadata(
            extension_id,
            expected=(ExtensionType.ADAPTER, ExtensionType.PLUGIN),
        )
        if not isinstance(receiver, ExtensionMessageReceiver):
            raise TypeError("receiver must implement receive_message()")
        with self._lock:
            if metadata.name in self._message_receivers:
                raise ExtensionRuntimeGatewayError(
                    f"message receiver already registered: {metadata.name}"
                )
            self._message_receivers[metadata.name] = receiver

    def dispatch(
        self,
        operation: ExtensionGatewayOperation | str,
        *,
        extension_id: str,
        **kwargs: Any,
    ) -> ExtensionGatewayResult | None:
        """Route an explicit operation to a typed Gateway method."""

        try:
            normalized = ExtensionGatewayOperation(operation)
        except (TypeError, ValueError) as exc:
            raise ExtensionRuntimeGatewayError(
                f"unsupported Extension Gateway operation: {operation}"
            ) from exc
        if normalized is ExtensionGatewayOperation.INVOKE_SKILL:
            return self.invoke_skill(extension_id, **kwargs)
        if normalized is ExtensionGatewayOperation.INVOKE_PLUGIN:
            return self.invoke_plugin(extension_id, **kwargs)
        return self.receive_message(extension_id, **kwargs)

    def invoke_skill(
        self,
        extension_id: str,
        *,
        request: SkillRequest,
        resolve_artifact: ArtifactResolver,
        publish_artifact: ArtifactPublisher,
        python_executable: str | None = None,
    ) -> ExtensionGatewayResult:
        metadata = self._metadata(extension_id, expected=(ExtensionType.SKILL,))
        if not isinstance(request, SkillRequest):
            raise TypeError("request must be a SkillRequest")
        if request.skill_id != metadata.name:
            raise ExtensionRuntimeGatewayError(
                "SkillRequest skill_id does not match the dispatched Extension"
            )
        request, context = self._skill_context(metadata, request)
        self._trace_operation(context, "skill.invoke.start")
        try:
            self._observe_health(metadata.name, context.trace_id)
            runtime_result = self.skill_invoker.invoke(
                request,
                resolve_artifact=resolve_artifact,
                publish_artifact=publish_artifact,
                event_publisher=None,
                python_executable=python_executable,
            )
            if not isinstance(runtime_result, SkillRuntimeResult):
                raise ExtensionRuntimeGatewayError(
                    "SkillInvoker must return SkillRuntimeResult"
                )
            if (
                runtime_result.descriptor.name != metadata.name
                or runtime_result.descriptor.version != metadata.version
            ):
                raise ExtensionRuntimeGatewayError(
                    "Skill result identity does not match Registry metadata"
                )
            artifacts = self._merge_artifacts(request.files, runtime_result.artifacts)
            context = context.with_outputs(
                artifacts=artifacts,
                events=runtime_result.events,
            )
            for event in runtime_result.events:
                self.trace_store.record_stream_event(metadata.name, event)
                self.streaming_bridge.publish(event)
            runtime_result = SkillRuntimeResult(
                descriptor=runtime_result.descriptor,
                result=runtime_result.result,
                published_event_count=len(runtime_result.events),
            )
        except Exception as exc:
            self._record_failure(context, "skill.invoke.failure", exc)
            raise
        self.metrics_store.record_call(metadata.name, success=True)
        self._trace_operation(context, "skill.invoke.success")
        return ExtensionGatewayResult(
            operation=ExtensionGatewayOperation.INVOKE_SKILL,
            context=context,
            value=runtime_result,
        )

    def invoke_plugin(
        self,
        extension_id: str,
        *,
        payload: Mapping[str, Any],
        trace_id: str | None = None,
        session_id: str | None = None,
    ) -> ExtensionGatewayResult:
        metadata = self._metadata(extension_id, expected=(ExtensionType.PLUGIN,))
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        with self._lock:
            invoker = self._plugin_invokers.get(metadata.name)
        if invoker is None:
            raise ExtensionNotAvailableError(
                f"Plugin invocation facade is not registered: {metadata.name}"
            )
        context = self._new_context(
            metadata,
            trace_id=trace_id,
            session_id=session_id,
        )
        self._trace_operation(context, "plugin.invoke.start")
        try:
            self._observe_health(metadata.name, context.trace_id, component=invoker)
            value = invoker.invoke(context, payload)
        except Exception as exc:
            self._record_failure(context, "plugin.invoke.failure", exc)
            raise
        self.metrics_store.record_call(metadata.name, success=True)
        self._trace_operation(context, "plugin.invoke.success")
        return ExtensionGatewayResult(
            operation=ExtensionGatewayOperation.INVOKE_PLUGIN,
            context=context,
            value=value,
        )

    def receive_message(self, extension_id: str) -> ExtensionGatewayResult | None:
        metadata = self._metadata(
            extension_id,
            expected=(ExtensionType.ADAPTER, ExtensionType.PLUGIN),
        )
        with self._lock:
            receiver = self._message_receivers.get(metadata.name)
        if receiver is None:
            raise ExtensionNotAvailableError(
                f"message receiver is not registered: {metadata.name}"
            )
        provisional = self._new_context(metadata)
        try:
            self._observe_health(metadata.name, None, component=receiver)
            message = receiver.receive_message()
            if message is None:
                context = provisional
            else:
                if not isinstance(message, MessageEvent):
                    raise ExtensionRuntimeGatewayError(
                        "message receiver must return MessageEvent or None"
                    )
                if message.channel.type != metadata.name:
                    raise ExtensionRuntimeGatewayError(
                        "MessageEvent channel does not match receiver Extension"
                    )
                context = ExtensionRuntimeContext(
                    extension_id=metadata.name,
                    version=metadata.version,
                    trace_id=message.trace_id,
                    session_id=message.session_id,
                    artifacts=message.attachments,
                )
        except Exception as exc:
            self._record_failure(provisional, "adapter.receive.failure", exc)
            raise
        self.metrics_store.record_call(metadata.name, success=True)
        self._trace_operation(
            context,
            "adapter.message.received" if message is not None else "adapter.receive.empty",
            metadata=(
                {"message_id": message.id, "channel": message.channel.type}
                if message is not None
                else {}
            ),
        )
        if message is None:
            return None
        return ExtensionGatewayResult(
            operation=ExtensionGatewayOperation.RECEIVE_MESSAGE,
            context=context,
            value=message,
        )

    def _observe_health(
        self,
        extension_id: str,
        trace_id: str | None,
        *,
        component: object | None = None,
    ) -> HealthReport:
        health_check = getattr(component, "health_check", None)
        report = (
            health_check()
            if callable(health_check)
            else self.lifecycle_manager.health(extension_id)
        )
        if not isinstance(report, HealthReport):
            raise ExtensionRuntimeGatewayError(
                "Extension health check must return HealthReport"
            )
        if report.name != extension_id:
            raise ExtensionRuntimeGatewayError(
                "Extension health identity does not match dispatched Extension"
            )
        self.health_store.record_health(report, trace_id=trace_id)
        self.health_store.record_state(self.lifecycle_manager.get(extension_id))
        if not report.healthy:
            raise ExtensionNotAvailableError(
                f"Extension is not healthy: {extension_id} ({report.code})"
            )
        return report

    def _metadata(
        self,
        extension_id: str,
        *,
        expected: tuple[ExtensionType, ...],
    ) -> ExtensionMetadata:
        if not isinstance(extension_id, str) or not extension_id.strip():
            raise ValueError("extension_id must be non-empty text")
        metadata = self.registry.get(extension_id)
        if metadata is None:
            raise ExtensionNotAvailableError(
                f"Extension is not registered: {extension_id}"
            )
        if metadata.type not in expected:
            allowed = ", ".join(item.value for item in expected)
            raise ExtensionRuntimeGatewayError(
                f"{extension_id} must have Extension type: {allowed}"
            )
        return metadata

    def _skill_context(
        self, metadata: ExtensionMetadata, request: SkillRequest
    ) -> tuple[SkillRequest, ExtensionRuntimeContext]:
        request_context = dict(request.context)
        trace_id = self._optional_text(request_context.get("trace_id"))
        session_id = self._optional_text(request_context.get("session_id"))
        context = self._new_context(
            metadata,
            trace_id=trace_id,
            session_id=session_id,
            artifacts=request.files,
        )
        request_context["trace_id"] = context.trace_id
        request_context["session_id"] = context.session_id
        normalized_request = SkillRequest(
            request_id=request.request_id,
            skill_id=request.skill_id,
            files=request.files,
            parameters=request.parameters,
            context=request_context,
        )
        return normalized_request, context

    def _new_context(
        self,
        metadata: ExtensionMetadata,
        *,
        trace_id: str | None = None,
        session_id: str | None = None,
        artifacts: tuple[Artifact, ...] = (),
    ) -> ExtensionRuntimeContext:
        return ExtensionRuntimeContext(
            extension_id=metadata.name,
            version=metadata.version,
            trace_id=trace_id or f"trc_ext_{self._next_id()}",
            session_id=session_id or f"ses_ext_{self._next_id()}",
            artifacts=artifacts,
        )

    def _trace_operation(
        self,
        context: ExtensionRuntimeContext,
        event_type: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.trace_store.record(
            context.extension_id,
            trace_id=context.trace_id,
            event_id=f"evt_gateway_{self._next_id()}",
            event_type=event_type,
            session_id=context.session_id,
            metadata=metadata,
        )

    def _record_failure(
        self,
        context: ExtensionRuntimeContext,
        event_type: str,
        error: Exception,
    ) -> None:
        self.metrics_store.record_call(context.extension_id, success=False)
        self._trace_operation(
            context,
            event_type,
            metadata={"error_type": type(error).__name__},
        )

    def _next_id(self) -> str:
        with self._lock:
            value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise ExtensionRuntimeGatewayError(
                "id_factory must return non-empty text"
            )
        return value.strip()

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ExtensionRuntimeGatewayError(
                "trace_id and session_id must be non-empty text when provided"
            )
        return value.strip()

    @staticmethod
    def _merge_artifacts(
        inputs: tuple[Artifact, ...], outputs: tuple[Artifact, ...]
    ) -> tuple[Artifact, ...]:
        merged: dict[str, Artifact] = {item.id: item for item in inputs}
        for artifact in outputs:
            existing = merged.get(artifact.id)
            if existing is not None and existing != artifact:
                raise ExtensionRuntimeGatewayError(
                    f"Artifact identifier collision: {artifact.id}"
                )
            merged[artifact.id] = artifact
        return tuple(merged.values())
