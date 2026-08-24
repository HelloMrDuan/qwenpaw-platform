import json
import unittest

from core.contracts import (
    STREAM_SCHEMA_VERSION,
    StreamEvent,
    StreamEventType,
    StreamSequenceError,
    StreamSource,
    validate_stream_sequence,
)


class StreamingContractTests(unittest.TestCase):
    def event(
        self,
        event_type: StreamEventType,
        sequence: int,
        payload: dict | None = None,
        **changes: object,
    ) -> StreamEvent:
        default_payloads = {
            StreamEventType.AGENT_START: {"agent_id": "default"},
            StreamEventType.AGENT_THINKING: {"status": "working"},
            StreamEventType.MESSAGE_DELTA: {"delta": "hello", "format": "text"},
            StreamEventType.TOOL_START: {
                "tool_call_id": "call_001",
                "tool": "fixture-tool",
                "tool_type": "skill",
            },
            StreamEventType.TOOL_PROGRESS: {
                "tool_call_id": "call_001",
                "tool": "fixture-tool",
                "progress": {"percent": 50},
            },
            StreamEventType.TOOL_RESULT: {
                "tool_call_id": "call_001",
                "tool": "fixture-tool",
                "status": "succeeded",
            },
            StreamEventType.TOOL_ERROR: {
                "tool_call_id": "call_001",
                "tool": "fixture-tool",
                "error": {"code": "FAILED"},
            },
            StreamEventType.FILE_CREATED: {
                "tool_call_id": "call_001",
                "artifact": {"id": "art_001"},
            },
            StreamEventType.AGENT_DONE: {"final": "hello", "artifacts": []},
            StreamEventType.AGENT_ERROR: {
                "error": {"code": "AGENT_FAILED", "message": "safe"}
            },
            StreamEventType.AGENT_CANCELLED: {"reason": "user"},
        }
        values = {
            "version": STREAM_SCHEMA_VERSION,
            "event_id": f"evt_{sequence:03d}",
            "event": event_type,
            "stream_id": "str_001",
            "sequence": sequence,
            "timestamp": "2026-08-24T08:30:00Z",
            "trace_id": "trc_001",
            "session_id": "ses_001",
            "conversation_id": "conv_001",
            "task_id": "task_001",
            "source": StreamSource(type="test", name="contract-fixture"),
            "payload": default_payloads[event_type] if payload is None else payload,
        }
        values.update(changes)
        return StreamEvent(**values)

    def test_required_event_types_are_supported(self) -> None:
        required = {
            "agent.start",
            "agent.thinking",
            "message.delta",
            "tool.start",
            "tool.progress",
            "tool.result",
            "file.created",
            "agent.done",
            "tool.error",
            "agent.error",
        }
        self.assertTrue(required.issubset({item.value for item in StreamEventType}))

    def test_json_round_trip(self) -> None:
        original = self.event(StreamEventType.MESSAGE_DELTA, 2)
        encoded = json.dumps(original.to_dict())
        decoded = StreamEvent.from_dict(json.loads(encoded))

        self.assertEqual(decoded, original)
        self.assertIn('"schema_version": "stream.v1"', encoded)

    def test_valid_agent_and_tool_sequence(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1),
            self.event(StreamEventType.TOOL_START, 2),
            self.event(StreamEventType.TOOL_PROGRESS, 3),
            self.event(StreamEventType.FILE_CREATED, 4),
            self.event(StreamEventType.TOOL_RESULT, 5),
            self.event(StreamEventType.MESSAGE_DELTA, 6),
            self.event(StreamEventType.AGENT_DONE, 7),
        ]
        validate_stream_sequence(events)

    def test_rejects_non_increasing_sequence(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1),
            self.event(StreamEventType.MESSAGE_DELTA, 1, event_id="evt_duplicate"),
            self.event(StreamEventType.AGENT_DONE, 2),
        ]
        with self.assertRaisesRegex(StreamSequenceError, "strictly increasing"):
            validate_stream_sequence(events)

    def test_rejects_duplicate_event_id(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1, event_id="evt_same"),
            self.event(StreamEventType.MESSAGE_DELTA, 2, event_id="evt_same"),
            self.event(StreamEventType.AGENT_DONE, 3),
        ]
        with self.assertRaisesRegex(StreamSequenceError, "event_id values must be unique"):
            validate_stream_sequence(events)

    def test_rejects_tool_progress_without_start(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1),
            self.event(StreamEventType.TOOL_PROGRESS, 2),
            self.event(StreamEventType.AGENT_DONE, 3),
        ]
        with self.assertRaisesRegex(StreamSequenceError, "preceding tool.start"):
            validate_stream_sequence(events)

    def test_rejects_event_after_terminal(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1),
            self.event(StreamEventType.AGENT_DONE, 2),
            self.event(StreamEventType.MESSAGE_DELTA, 3),
        ]
        with self.assertRaisesRegex(StreamSequenceError, "after an Agent terminal"):
            validate_stream_sequence(events)

    def test_rejects_invalid_progress(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            self.event(
                StreamEventType.TOOL_PROGRESS,
                2,
                payload={
                    "tool_call_id": "call_001",
                    "tool": "fixture-tool",
                    "progress": {"percent": 120},
                },
            )

    def test_rejects_decreasing_tool_progress(self) -> None:
        events = [
            self.event(StreamEventType.AGENT_START, 1),
            self.event(StreamEventType.TOOL_START, 2),
            self.event(
                StreamEventType.TOOL_PROGRESS,
                3,
                payload={
                    "tool_call_id": "call_001",
                    "tool": "fixture-tool",
                    "progress": {"percent": 80},
                },
            ),
            self.event(
                StreamEventType.TOOL_PROGRESS,
                4,
                payload={
                    "tool_call_id": "call_001",
                    "tool": "fixture-tool",
                    "progress": {"percent": 40},
                },
            ),
            self.event(StreamEventType.TOOL_RESULT, 5),
            self.event(StreamEventType.AGENT_DONE, 6),
        ]
        with self.assertRaisesRegex(StreamSequenceError, "cannot decrease"):
            validate_stream_sequence(events)


if __name__ == "__main__":
    unittest.main()
