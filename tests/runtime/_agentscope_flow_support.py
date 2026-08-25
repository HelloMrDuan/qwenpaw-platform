from __future__ import annotations

from itertools import count

from core.contracts import MessageEvent
from core.extensions.lifecycle import (
    ExtensionState,
    HealthReport,
    LifecycleAction,
    LifecycleRecord,
)
from core.extensions.observability import ExtensionMetricsStore, ExtensionTraceStore
from core.extensions.runtime import ExtensionRuntimeGateway
from core.streaming import StreamingBridge


class AgentMock:
    def __init__(self, response: str) -> None:
        self.response = response
        self.received: list[MessageEvent] = []

    def respond(self, message: MessageEvent) -> str:
        self.received.append(message)
        return self.response


class StaticRunningLifecycle:
    """Read-only local state used when packaging a large recovered tree is out of scope."""

    def __init__(self, metadata) -> None:
        self.record = LifecycleRecord(
            name=metadata.name,
            type=metadata.type,
            version=metadata.version,
            package_sha256="0" * 64,
            state=ExtensionState.RUNNING,
            revision=1,
            last_action=LifecycleAction.INSTALL,
        )

    def get(self, name: str) -> LifecycleRecord:
        if name != self.record.name:
            raise KeyError(name)
        return self.record

    def health(self, name: str) -> HealthReport:
        record = self.get(name)
        return HealthReport(
            name=record.name,
            version=record.version,
            state=record.state,
            healthy=True,
            deployment_verified=True,
            runtime_probe_performed=False,
            code="OFFLINE_FIXTURE_VERIFIED",
            message="offline lifecycle fixture; no process was started",
        )


def build_receive_gateway(registry, lifecycle, name: str, receiver):
    metrics = ExtensionMetricsStore()
    traces = ExtensionTraceStore()
    identifiers = count(1)
    gateway = ExtensionRuntimeGateway(
        registry,
        lifecycle,
        skill_invoker=None,  # type: ignore[arg-type] -- receive-only validation
        streaming_bridge=StreamingBridge(),
        metrics_store=metrics,
        trace_store=traces,
        message_receivers={name: receiver},
        id_factory=lambda: f"offline-{next(identifiers)}",
    )
    return gateway, metrics, traces
