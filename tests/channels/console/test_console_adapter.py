from __future__ import annotations

import asyncio
from io import StringIO
import unittest

from adapters.channels.console import ConsoleChannelAdapter
from core.contracts import (
    Artifact,
    ArtifactKind,
    ChannelAdapter,
    DeliveryStatus,
    MessageEvent,
    StreamEvent,
    StreamEventType,
    StreamSource,
    STREAM_SCHEMA_VERSION,
)


def stream_event(
    message: MessageEvent,
    event_type: StreamEventType,
    sequence: int,
    payload: dict,
) -> StreamEvent:
    return StreamEvent(
        version=STREAM_SCHEMA_VERSION,
        event_id=f"evt_console_{sequence}",
        event=event_type,
        stream_id="str_console_e2e",
        sequence=sequence,
        timestamp="2026-08-25T02:00:01Z",
        trace_id=message.trace_id,
        session_id=message.session_id,
        conversation_id=message.conversation_id,
        task_id="task_console_e2e",
        source=StreamSource(
            type="agent" if event_type.value.startswith("agent.") else "skill",
            name="fixture",
        ),
        payload=payload,
    )


class ConsoleChannelAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output = StringIO()
        self.adapter = ConsoleChannelAdapter(output=self.output)

    def test_parse_message_normalizes_console_input(self) -> None:
        self.assertIsInstance(self.adapter, ChannelAdapter)

        message = self.adapter.parse_message(
            {
                "text": "处理本地任务",
                "user_id": "local-user",
                "platform_user_id": "usr_local",
                "display_name": "Local User",
                "message_id": "input-001",
                "trace_id": "trc_console_001",
                "session_id": "ses_console_001",
                "conversation_id": "conv_console_001",
                "timestamp": "2026-08-25T02:00:00Z",
                "metadata": {"locale": "zh-CN"},
            }
        )

        self.assertEqual(message.channel.type, "console")
        self.assertEqual(message.channel.instance_id, "console-local")
        self.assertEqual(message.channel.message_id, "input-001")
        self.assertEqual(message.user.id, "usr_local")
        self.assertEqual(message.user.external_id, "local-user")
        self.assertEqual(message.session_id, "ses_console_001")
        self.assertEqual(message.conversation_id, "conv_console_001")
        self.assertEqual(message.content.text, "处理本地任务")
        self.assertEqual(message.metadata["input_mode"], "console")
        self.assertEqual(MessageEvent.from_dict(message.to_dict()), message)

    def test_parse_message_rejects_empty_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "payload.text"):
            self.adapter.parse_message({"text": ""})

    def test_send_message_writes_text_artifact_and_receipt(self) -> None:
        artifact = Artifact(
            id="art_console",
            kind=ArtifactKind.FILE,
            name="result.pdf",
            mime_type="application/pdf",
            size_bytes=256,
            uri="artifact://outputs/result.pdf",
        )

        receipt = asyncio.run(
            self.adapter.send_message(
                "ses_console",
                "完整回复",
                artifacts=(artifact,),
                metadata={"mode": "complete"},
            )
        )

        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.channel, "console")
        self.assertEqual(receipt.metadata["artifact_ids"], ["art_console"])
        self.assertEqual(
            self.output.getvalue(),
            "完整回复\n[file] result.pdf (artifact://outputs/result.pdf)\n",
        )

    def test_end_to_end_message_stream_renderer_console_output(self) -> None:
        message = self.adapter.parse_message(
            {
                "text": "生成报告",
                "user_id": "local-user",
                "message_id": "input-e2e",
                "trace_id": "trc_console_e2e",
                "session_id": "ses_console_e2e",
                "conversation_id": "conv_console_e2e",
                "timestamp": "2026-08-25T02:00:00Z",
            }
        )
        artifact = Artifact(
            id="art_output",
            kind=ArtifactKind.FILE,
            name="output.pdf",
            mime_type="application/pdf",
            size_bytes=512,
            uri="artifact://outputs/output.pdf",
        )
        events = (
            stream_event(
                message,
                StreamEventType.AGENT_START,
                1,
                {"agent_id": "agent_fixture"},
            ),
            stream_event(
                message,
                StreamEventType.MESSAGE_DELTA,
                2,
                {"delta": "收到。", "format": "text"},
            ),
            stream_event(
                message,
                StreamEventType.TOOL_START,
                3,
                {"tool_call_id": "call_pdf", "tool": "pdf-editor"},
            ),
            stream_event(
                message,
                StreamEventType.TOOL_PROGRESS,
                4,
                {
                    "tool_call_id": "call_pdf",
                    "tool": "pdf-editor",
                    "progress": {"percent": 50},
                    "message": "正在处理文件",
                },
            ),
            stream_event(
                message,
                StreamEventType.FILE_CREATED,
                5,
                {
                    "tool_call_id": "call_pdf",
                    "artifact": artifact.to_dict(),
                },
            ),
            stream_event(
                message,
                StreamEventType.TOOL_RESULT,
                6,
                {
                    "tool_call_id": "call_pdf",
                    "tool": "pdf-editor",
                    "status": "succeeded",
                    "summary": "PDF 完成",
                },
            ),
            stream_event(
                message,
                StreamEventType.MESSAGE_DELTA,
                7,
                {"delta": "完成。", "format": "text"},
            ),
            stream_event(
                message,
                StreamEventType.AGENT_DONE,
                8,
                {"final": "收到。完成。"},
            ),
        )

        async def deliver() -> list:
            return [await self.adapter.send_stream_event(item) for item in events]

        receipts = asyncio.run(deliver())
        rendered = self.output.getvalue()

        self.assertEqual(message.channel.type, "console")
        self.assertEqual(message.session_id, events[0].session_id)
        self.assertIn("[status] 任务已开始", rendered)
        self.assertIn("收到。", rendered)
        self.assertIn("[status] 开始执行 pdf-editor", rendered)
        self.assertIn("[status] 正在处理文件", rendered)
        self.assertIn(
            "[file] output.pdf (artifact://outputs/output.pdf)", rendered
        )
        self.assertIn("[status] PDF 完成", rendered)
        self.assertTrue(rendered.endswith("完成。"))
        self.assertIsNone(receipts[-1])
        self.assertTrue(
            all(
                receipt is None or receipt.status is DeliveryStatus.SENT
                for receipt in receipts
            )
        )

    def test_error_event_is_visible_and_safe(self) -> None:
        message = self.adapter.parse_message(
            {
                "text": "失败测试",
                "session_id": "ses_error",
                "conversation_id": "conv_error",
            }
        )
        error_event = stream_event(
            message,
            StreamEventType.TOOL_ERROR,
            1,
            {
                "tool_call_id": "call_error",
                "tool": "fixture-tool",
                "error": {
                    "code": "FIXTURE_ERROR",
                    "message": "工具执行失败",
                },
            },
        )

        receipt = asyncio.run(self.adapter.send_stream_event(error_event))

        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(self.output.getvalue(), "[error] 工具执行失败\n")


if __name__ == "__main__":
    unittest.main()
