from __future__ import annotations

from datetime import datetime, timezone
import unittest

from core.contracts import (
    STREAM_SCHEMA_VERSION,
    StreamEvent,
    StreamEventType,
    StreamSource,
)
from core.extensions import ExtensionType
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


FIXED_TIME = datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc)


def _health(
    name: str,
    *,
    healthy: bool,
    state: ExtensionState = ExtensionState.RUNNING,
) -> HealthReport:
    return HealthReport(
        name=name,
        version="1.0.0",
        state=state,
        healthy=healthy,
        deployment_verified=True,
        runtime_probe_performed=True,
        code="SERVICE_RUNNING" if healthy else "SERVICE_FAILED",
        message="healthy" if healthy else "unhealthy",
    )


def _lifecycle(name: str, state: ExtensionState) -> LifecycleRecord:
    return LifecycleRecord(
        name=name,
        type=ExtensionType.PLUGIN,
        version="1.0.0",
        package_sha256="a" * 64,
        state=state,
        revision=1,
        last_action=LifecycleAction.INSTALL,
    )


def _stream_event(
    *,
    extension_name: str,
    event_id: str,
    trace_id: str,
    sequence: int,
) -> StreamEvent:
    return StreamEvent(
        version=STREAM_SCHEMA_VERSION,
        event_id=event_id,
        event=StreamEventType.TOOL_START,
        stream_id="stream-observability-test",
        sequence=sequence,
        timestamp="2026-08-25T10:00:00Z",
        trace_id=trace_id,
        session_id="session-observability-test",
        conversation_id="conversation-observability-test",
        task_id="task-observability-test",
        source=StreamSource(type="skill", name=extension_name),
        payload={"tool_call_id": f"call-{event_id}", "tool": extension_name},
    )


class ExtensionObservabilityTests(unittest.TestCase):
    def test_health_and_lifecycle_history_are_recorded_without_mutation(self) -> None:
        store = ExtensionHealthStore(
            max_history_per_extension=2,
            clock=lambda: FIXED_TIME,
        )
        running = _lifecycle("hermes", ExtensionState.RUNNING)
        first = _health("hermes", healthy=True)
        second = _health("hermes", healthy=False, state=ExtensionState.FAILED)

        state_observation = store.record_state(running)
        first_observation = store.record_health(first, trace_id="trace-health-001")
        second_observation = store.record_health(second)

        self.assertEqual(state_observation.state, ExtensionState.RUNNING)
        self.assertEqual(store.latest_state("hermes"), state_observation)
        self.assertEqual(
            store.health_history("hermes"),
            (first_observation, second_observation),
        )
        self.assertEqual(store.latest_health("hermes"), second_observation)
        self.assertEqual(first_observation.trace_id, "trace-health-001")
        self.assertEqual(first.state, ExtensionState.RUNNING)
        self.assertEqual(second.code, "SERVICE_FAILED")

    def test_metrics_count_calls_successes_and_failures(self) -> None:
        metrics = ExtensionMetricsStore(clock=lambda: FIXED_TIME)

        metrics.record_call("pdf-editor", success=True)
        metrics.record_call("pdf-editor", success=False)
        snapshot = metrics.record_call("pdf-editor", success=True)

        self.assertEqual(snapshot.calls, 3)
        self.assertEqual(snapshot.successes, 2)
        self.assertEqual(snapshot.failures, 1)
        self.assertEqual(snapshot.updated_at, "2026-08-25T10:00:00.000000Z")
        self.assertEqual(metrics.get("pdf-editor"), snapshot)
        self.assertEqual(metrics.list(), (snapshot,))

    def test_stream_and_generic_events_share_trace_correlation(self) -> None:
        traces = ExtensionTraceStore(clock=lambda: FIXED_TIME)
        stream = _stream_event(
            extension_name="pdf-editor",
            event_id="event-pdf-start",
            trace_id="trace-shared-001",
            sequence=1,
        )

        pdf_event = traces.record_stream_event("pdf-editor", stream)
        telegram_event = traces.record(
            "telegram",
            trace_id="trace-shared-001",
            event_id="event-telegram-delivery",
            event_type="delivery.sent",
            session_id="session-observability-test",
            metadata={"provider_message_id": "fake-provider-id"},
        )

        self.assertEqual(
            traces.trace("trace-shared-001"),
            (pdf_event, telegram_event),
        )
        self.assertEqual(
            traces.trace("trace-shared-001", extension_name="pdf-editor"),
            (pdf_event,),
        )
        self.assertEqual(pdf_event.event_type, "tool.start")
        self.assertEqual(pdf_event.metadata["source_name"], "pdf-editor")
        self.assertEqual(telegram_event.event_type, "delivery.sent")

    def test_multiple_extensions_are_isolated_in_all_stores(self) -> None:
        health = ExtensionHealthStore(clock=lambda: FIXED_TIME)
        metrics = ExtensionMetricsStore(clock=lambda: FIXED_TIME)
        traces = ExtensionTraceStore(clock=lambda: FIXED_TIME)

        for name, success in (("telegram", True), ("wecom", False)):
            health.record_state(_lifecycle(name, ExtensionState.ENABLED))
            health.record_health(
                _health(
                    name,
                    healthy=success,
                    state=(
                        ExtensionState.RUNNING
                        if success
                        else ExtensionState.FAILED
                    ),
                )
            )
            metrics.record_call(name, success=success)
            traces.record(
                name,
                trace_id=f"trace-{name}",
                event_id="event-001",
                event_type="extension.call",
            )

        self.assertEqual(health.extension_names(), ("telegram", "wecom"))
        self.assertTrue(health.latest_health("telegram").healthy)
        self.assertFalse(health.latest_health("wecom").healthy)
        self.assertEqual(metrics.get("telegram").successes, 1)
        self.assertEqual(metrics.get("telegram").failures, 0)
        self.assertEqual(metrics.get("wecom").successes, 0)
        self.assertEqual(metrics.get("wecom").failures, 1)
        self.assertEqual(len(traces.for_extension("telegram")), 1)
        self.assertEqual(len(traces.for_extension("wecom")), 1)
        self.assertEqual(traces.trace("trace-telegram")[0].extension_name, "telegram")
        self.assertEqual(traces.trace("trace-wecom")[0].extension_name, "wecom")


if __name__ == "__main__":
    unittest.main()
