from __future__ import annotations

import unittest

from core.contracts import (
    STREAM_SCHEMA_VERSION,
    StreamConsumer,
    StreamEvent,
    StreamEventType,
    StreamSequenceError,
    StreamSource,
)
from core.streaming import StreamCollector, StreamingBridge


def stream_event(
    event_type: StreamEventType,
    sequence: int,
    *,
    stream_id: str = "str_bridge",
    session_id: str = "ses_bridge",
    event_id: str | None = None,
) -> StreamEvent:
    tool_payload = {"tool_call_id": "call_bridge", "tool": "fixture-tool"}
    payloads = {
        StreamEventType.AGENT_START: {"agent_id": "agent_fixture"},
        StreamEventType.TOOL_START: tool_payload,
        StreamEventType.TOOL_PROGRESS: {
            **tool_payload,
            "progress": {"percent": 50},
        },
        StreamEventType.FILE_CREATED: {
            **tool_payload,
            "artifact": {"id": "art_bridge"},
        },
        StreamEventType.TOOL_RESULT: {**tool_payload, "status": "succeeded"},
        StreamEventType.TOOL_ERROR: {
            **tool_payload,
            "error": {"code": "FIXTURE_ERROR", "message": "expected"},
        },
        StreamEventType.AGENT_DONE: {"final": "done"},
    }
    return StreamEvent(
        version=STREAM_SCHEMA_VERSION,
        event_id=event_id or f"evt_{stream_id}_{sequence}",
        event=event_type,
        stream_id=stream_id,
        sequence=sequence,
        timestamp="2026-08-24T12:00:00Z",
        trace_id=f"trc_{stream_id}",
        session_id=session_id,
        conversation_id=f"conv_{session_id}",
        task_id=f"task_{stream_id}",
        source=StreamSource(type="skill", name="fixture-tool"),
        payload=payloads[event_type],
    )


class StreamingBridgeTests(unittest.TestCase):
    def test_event_publish_is_available_for_session_replay(self) -> None:
        bridge = StreamingBridge()
        event = stream_event(StreamEventType.TOOL_START, 1)

        bridge.publish(event)

        self.assertEqual(bridge.replay("ses_bridge"), (event,))

    def test_subscriber_receives_events_until_unsubscribed(self) -> None:
        bridge = StreamingBridge()
        collector = StreamCollector()
        self.assertIsInstance(collector, StreamConsumer)
        unsubscribe = bridge.subscribe(collector)

        start = stream_event(StreamEventType.TOOL_START, 1)
        done = stream_event(StreamEventType.TOOL_RESULT, 2)
        bridge.publish(start)
        unsubscribe()
        bridge.publish(done)

        self.assertEqual(collector.events, (start,))
        self.assertEqual(bridge.replay("ses_bridge"), (start, done))

    def test_replay_is_isolated_by_session_and_preserves_publish_order(self) -> None:
        bridge = StreamingBridge()
        first = stream_event(StreamEventType.TOOL_START, 1)
        other = stream_event(
            StreamEventType.TOOL_START,
            1,
            stream_id="str_other",
            session_id="ses_other",
        )
        second = stream_event(StreamEventType.TOOL_RESULT, 2)

        bridge.publish(first)
        bridge.publish(other)
        bridge.publish(second)

        self.assertEqual(bridge.replay("ses_bridge"), (first, second))
        self.assertEqual(bridge.replay("ses_other"), (other,))
        self.assertEqual(bridge.replay("ses_missing"), ())

    def test_order_event_id_and_session_correlation_are_enforced(self) -> None:
        bridge = StreamingBridge()
        start = stream_event(StreamEventType.TOOL_START, 1)
        bridge.publish(start)

        with self.assertRaisesRegex(StreamSequenceError, "strictly increasing"):
            bridge.publish(
                stream_event(
                    StreamEventType.TOOL_PROGRESS,
                    1,
                    event_id="evt_non_increasing",
                )
            )
        with self.assertRaisesRegex(StreamSequenceError, "event_id values"):
            bridge.publish(
                stream_event(StreamEventType.TOOL_PROGRESS, 2, event_id=start.event_id)
            )
        with self.assertRaisesRegex(StreamSequenceError, "session fields"):
            bridge.publish(
                stream_event(
                    StreamEventType.TOOL_PROGRESS,
                    2,
                    session_id="ses_changed",
                    event_id="evt_changed_session",
                )
            )

        self.assertEqual(bridge.replay("ses_bridge"), (start,))

    def test_tool_error_is_delivered_and_closes_the_tool_call(self) -> None:
        bridge = StreamingBridge()
        collector = StreamCollector()
        bridge.subscribe(collector)
        start = stream_event(StreamEventType.TOOL_START, 1)
        error = stream_event(StreamEventType.TOOL_ERROR, 2)

        bridge.publish(start)
        bridge.publish(error)

        self.assertEqual(
            [event.event for event in collector.events],
            [StreamEventType.TOOL_START, StreamEventType.TOOL_ERROR],
        )
        with self.assertRaisesRegex(StreamSequenceError, "preceding tool.start"):
            bridge.publish(stream_event(StreamEventType.TOOL_PROGRESS, 3))


if __name__ == "__main__":
    unittest.main()
