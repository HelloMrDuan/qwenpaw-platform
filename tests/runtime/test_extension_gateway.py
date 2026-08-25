from __future__ import annotations

from itertools import count
from pathlib import Path
import unittest

from core.contracts import (
    MESSAGE_SCHEMA_VERSION,
    STREAM_SCHEMA_VERSION,
    Artifact,
    ArtifactKind,
    ChannelRef,
    MessageContent,
    MessageEvent,
    MessageType,
    SkillRequest,
    SkillResult,
    StreamEvent,
    StreamEventType,
    StreamSource,
    UserRef,
)
from core.extensions import ExtensionRegistry, ExtensionRuntime, ExtensionType
from core.extensions.lifecycle import (
    ExtensionState,
    HealthReport,
    LifecycleAction,
    LifecycleRecord,
)
from core.extensions.observability import (
    ExtensionHealthStore,
    ExtensionMetricsStore,
    ExtensionTraceStore,
)
from core.extensions.runtime import (
    ExtensionGatewayOperation,
    ExtensionRuntimeGateway,
    ExtensionRuntimeGatewayError,
    SkillExecutorDescriptor,
    SkillRuntimeResult,
)
from core.streaming import StreamCollector, StreamingBridge


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class _FakeLifecycleManager:
    def __init__(self, registry: ExtensionRegistry) -> None:
        self.registry = registry
        self.health_calls: list[str] = []
        self.get_calls: list[str] = []

    def get(self, name: str) -> LifecycleRecord:
        self.get_calls.append(name)
        metadata = self.registry.get(name)
        if metadata is None:
            raise ValueError(f"not installed: {name}")
        return LifecycleRecord(
            name=metadata.name,
            type=metadata.type,
            version=metadata.version,
            package_sha256="a" * 64,
            state=ExtensionState.ENABLED,
            revision=2,
            last_action=LifecycleAction.ENABLE,
        )

    def health(self, name: str) -> HealthReport:
        self.health_calls.append(name)
        record = self.get(name)
        return HealthReport(
            name=record.name,
            version=record.version,
            state=record.state,
            healthy=True,
            deployment_verified=True,
            runtime_probe_performed=False,
            code="OFFLINE_TEST_HEALTHY",
            message="fake local deployment is healthy",
        )


class _FakeSkillInvoker:
    def __init__(self) -> None:
        self.requests: list[SkillRequest] = []

    def invoke(self, request: SkillRequest, **kwargs) -> SkillRuntimeResult:
        self.requests.append(request)
        if kwargs["event_publisher"] is not None:
            raise AssertionError("Gateway must validate before publishing Skill events")
        output = Artifact(
            id="artifact-gateway-output",
            kind=ArtifactKind.FILE,
            name="gateway-output.pdf",
            mime_type="application/pdf",
            size_bytes=200,
            uri="artifact://outputs/gateway-output.pdf",
            sha256="b" * 64,
        )
        correlation = {
            "stream_id": f"stream-{request.request_id}",
            "trace_id": request.context["trace_id"],
            "session_id": request.context["session_id"],
            "conversation_id": f"conversation-{request.request_id}",
            "task_id": f"task-{request.request_id}",
        }
        source = StreamSource(type="skill", name="pdf-editor")
        common = {
            "version": STREAM_SCHEMA_VERSION,
            "timestamp": "2026-08-25T11:00:00Z",
            "source": source,
            **correlation,
        }
        events = (
            StreamEvent(
                event_id="event-gateway-skill-start",
                event=StreamEventType.TOOL_START,
                sequence=1,
                payload={"tool_call_id": "call-gateway", "tool": "pdf-editor"},
                **common,
            ),
            StreamEvent(
                event_id="event-gateway-skill-file",
                event=StreamEventType.FILE_CREATED,
                sequence=2,
                payload={
                    "tool_call_id": "call-gateway",
                    "artifact": output.to_dict(),
                },
                **common,
            ),
            StreamEvent(
                event_id="event-gateway-skill-result",
                event=StreamEventType.TOOL_RESULT,
                sequence=3,
                payload={
                    "tool_call_id": "call-gateway",
                    "tool": "pdf-editor",
                    "status": "success",
                },
                **common,
            ),
        )
        result = SkillResult(
            request_id=request.request_id,
            success=True,
            message="offline Gateway Skill result",
            artifacts=(output,),
            events=events,
        )
        descriptor = SkillExecutorDescriptor(
            name="pdf-editor",
            version="1.2.0",
            type=ExtensionType.SKILL,
            runtime=ExtensionRuntime.PYTHON,
            manifest_path=REPOSITORY_ROOT / "skills" / "pdf-editor" / "manifest.yaml",
            executor_path=(
                REPOSITORY_ROOT / "skills" / "pdf-editor" / "executor" / "main.py"
            ),
            callable_name="execute",
            declared_events=("tool.start", "file.created", "tool.result"),
            artifact_contract={"outputs": []},
        )
        return SkillRuntimeResult(
            descriptor=descriptor,
            result=result,
            published_event_count=0,
        )


class _FakePluginInvoker:
    def __init__(self) -> None:
        self.calls = []
        self.fail = False

    def invoke(self, context, payload):
        self.calls.append((context, dict(payload)))
        if self.fail:
            raise RuntimeError("offline fake Plugin failure")
        return {"accepted": True, "operation": payload.get("operation")}


class _FakeMessageReceiver:
    def __init__(self) -> None:
        self.messages = [
            MessageEvent(
                id="message-gateway-telegram",
                version=MESSAGE_SCHEMA_VERSION,
                trace_id="trace-adapter-message",
                channel=ChannelRef(
                    type="telegram",
                    instance_id="telegram-offline-test",
                    message_id="provider-message-001",
                    thread_id="chat-001",
                ),
                user=UserRef(id="user-001", external_id="provider-user-001"),
                session_id="session-adapter-message",
                conversation_id="conversation-adapter-message",
                timestamp="2026-08-25T11:00:00Z",
                type=MessageType.TEXT,
                content=MessageContent(text="Gateway Adapter测试消息"),
            )
        ]

    def receive_message(self):
        return self.messages.pop(0) if self.messages else None


class ExtensionRuntimeGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ExtensionRegistry(REPOSITORY_ROOT)
        self.registry.discover()
        self.lifecycle = _FakeLifecycleManager(self.registry)
        self.skill_invoker = _FakeSkillInvoker()
        self.plugin_invoker = _FakePluginInvoker()
        self.message_receiver = _FakeMessageReceiver()
        self.streaming = StreamingBridge()
        self.collector = StreamCollector()
        self.streaming.subscribe(self.collector)
        self.health = ExtensionHealthStore()
        self.metrics = ExtensionMetricsStore()
        self.traces = ExtensionTraceStore()
        identifiers = count(1)
        self.gateway = ExtensionRuntimeGateway(
            self.registry,
            self.lifecycle,
            skill_invoker=self.skill_invoker,
            streaming_bridge=self.streaming,
            health_store=self.health,
            metrics_store=self.metrics,
            trace_store=self.traces,
            plugin_invokers={"wecom": self.plugin_invoker},
            message_receivers={"telegram": self.message_receiver},
            id_factory=lambda: f"offline-{next(identifiers):04d}",
        )

    def test_skill_dispatch_generates_context_stream_trace_and_metrics(self) -> None:
        source = Artifact(
            id="artifact-gateway-input",
            kind=ArtifactKind.FILE,
            name="input.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            uri="artifact://inputs/input.pdf",
            sha256="a" * 64,
        )
        request = SkillRequest(
            request_id="request-extension-gateway",
            skill_id="pdf-editor",
            files=(source,),
            parameters={"command": "offline-test"},
        )

        result = self.gateway.dispatch(
            ExtensionGatewayOperation.INVOKE_SKILL,
            extension_id="pdf-editor",
            request=request,
            resolve_artifact=lambda artifact: Path(artifact.name),
            publish_artifact=lambda path: source,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.operation, ExtensionGatewayOperation.INVOKE_SKILL)
        self.assertEqual(result.context.extension_id, "pdf-editor")
        self.assertTrue(result.context.trace_id.startswith("trc_ext_offline-"))
        self.assertTrue(result.context.session_id.startswith("ses_ext_offline-"))
        self.assertEqual(len(result.context.artifacts), 2)
        self.assertEqual(len(result.context.events), 3)
        self.assertEqual(tuple(self.collector.events), result.context.events)
        self.assertEqual(
            self.streaming.replay(result.context.session_id), result.context.events
        )
        self.assertEqual(result.value.published_event_count, 3)
        self.assertEqual(
            self.skill_invoker.requests[0].context["trace_id"],
            result.context.trace_id,
        )
        self.assertEqual(self.metrics.get("pdf-editor").calls, 1)
        self.assertEqual(self.metrics.get("pdf-editor").successes, 1)
        trace_types = [
            item.event_type for item in self.traces.trace(result.context.trace_id)
        ]
        self.assertEqual(
            trace_types,
            [
                "skill.invoke.start",
                "tool.start",
                "file.created",
                "tool.result",
                "skill.invoke.success",
            ],
        )
        self.assertEqual(
            self.health.latest_health("pdf-editor").trace_id,
            result.context.trace_id,
        )
        self.assertEqual(self.health.latest_state("pdf-editor").state, ExtensionState.ENABLED)

    def test_plugin_dispatch_invokes_registered_facade_and_records_failure(self) -> None:
        result = self.gateway.invoke_plugin(
            "wecom",
            payload={"operation": "send", "text": "offline"},
            trace_id="trace-plugin-call",
            session_id="session-plugin-call",
        )

        self.assertEqual(result.value, {"accepted": True, "operation": "send"})
        self.assertEqual(result.context.trace_id, "trace-plugin-call")
        self.assertEqual(self.plugin_invoker.calls[0][1]["text"], "offline")
        self.assertEqual(self.metrics.get("wecom").successes, 1)

        self.plugin_invoker.fail = True
        with self.assertRaisesRegex(RuntimeError, "offline fake Plugin failure"):
            self.gateway.dispatch(
                "plugin.invoke",
                extension_id="wecom",
                payload={"operation": "fail"},
                trace_id="trace-plugin-failure",
                session_id="session-plugin-failure",
            )

        metrics = self.metrics.get("wecom")
        self.assertEqual(metrics.calls, 2)
        self.assertEqual(metrics.successes, 1)
        self.assertEqual(metrics.failures, 1)
        failure_trace = self.traces.trace("trace-plugin-failure")
        self.assertEqual(failure_trace[-1].event_type, "plugin.invoke.failure")
        self.assertEqual(failure_trace[-1].metadata["error_type"], "RuntimeError")

    def test_adapter_message_uses_message_correlation_and_counts_empty_poll(self) -> None:
        result = self.gateway.dispatch(
            "adapter.receive",
            extension_id="telegram",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result.value, MessageEvent)
        self.assertEqual(result.context.trace_id, "trace-adapter-message")
        self.assertEqual(result.context.session_id, "session-adapter-message")
        self.assertEqual(result.value.content.text, "Gateway Adapter测试消息")
        trace = self.traces.trace("trace-adapter-message")
        self.assertEqual(trace[-1].event_type, "adapter.message.received")
        self.assertEqual(trace[-1].metadata["channel"], "telegram")

        self.assertIsNone(self.gateway.receive_message("telegram"))
        metrics = self.metrics.get("telegram")
        self.assertEqual(metrics.calls, 2)
        self.assertEqual(metrics.successes, 2)
        self.assertEqual(metrics.failures, 0)
        self.assertEqual(len(self.health.health_history("telegram")), 2)

    def test_dispatch_rejects_type_mismatch_and_unknown_operation(self) -> None:
        with self.assertRaisesRegex(
            ExtensionRuntimeGatewayError, "must have Extension type"
        ):
            self.gateway.invoke_plugin("pdf-editor", payload={})
        with self.assertRaisesRegex(
            ExtensionRuntimeGatewayError, "unsupported Extension Gateway operation"
        ):
            self.gateway.dispatch("runtime.start", extension_id="wecom")


if __name__ == "__main__":
    unittest.main()
