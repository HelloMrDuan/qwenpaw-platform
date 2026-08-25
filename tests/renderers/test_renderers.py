from __future__ import annotations

import unittest

from core.contracts import (
    Artifact,
    ArtifactKind,
    RENDER_OUTPUT_SCHEMA_VERSION,
    RenderedOutput,
    RenderedOutputType,
    STREAM_SCHEMA_VERSION,
    StreamEvent,
    StreamEventType,
    StreamRenderer,
    StreamSource,
)
from core.renderers import (
    ConsoleRenderer,
    RendererClosedError,
    RenderOrderError,
    TelegramRenderer,
    WeChatRenderer,
    WeComRenderer,
)


def event(
    event_type: StreamEventType,
    sequence: int,
    *,
    payload: dict | None = None,
    event_id: str | None = None,
) -> StreamEvent:
    defaults = {
        StreamEventType.MESSAGE_DELTA: {"delta": "text", "format": "text"},
        StreamEventType.FILE_CREATED: {
            "artifact": Artifact(
                id="art_render",
                kind=ArtifactKind.FILE,
                name="report.pdf",
                mime_type="application/pdf",
                size_bytes=128,
                uri="artifact://outputs/report.pdf",
            ).to_dict()
        },
        StreamEventType.TOOL_ERROR: {
            "tool_call_id": "call_render",
            "tool": "fixture-tool",
            "error": {
                "code": "FIXTURE_ERROR",
                "message": "测试错误",
                "retryable": False,
            },
        },
        StreamEventType.AGENT_DONE: {"final": "final text"},
    }
    return StreamEvent(
        version=STREAM_SCHEMA_VERSION,
        event_id=event_id or f"evt_render_{sequence}",
        event=event_type,
        stream_id="str_render",
        sequence=sequence,
        timestamp="2026-08-25T01:00:00Z",
        trace_id="trc_render",
        session_id="ses_render",
        conversation_id="conv_render",
        task_id="task_render",
        source=StreamSource(type="agent", name="fixture"),
        payload=payload if payload is not None else defaults[event_type],
    )


class StreamRendererTests(unittest.TestCase):
    def test_console_converts_delta_and_output_round_trips(self) -> None:
        renderer = ConsoleRenderer()
        self.assertIsInstance(renderer, StreamRenderer)

        outputs = renderer.render(
            event(StreamEventType.MESSAGE_DELTA, 1, payload={"delta": "你好"})
        )

        self.assertEqual(len(outputs), 1)
        output = outputs[0]
        self.assertEqual(output.type, RenderedOutputType.TEXT_DELTA)
        self.assertEqual(output.text, "你好")
        self.assertEqual(output.version, RENDER_OUTPUT_SCHEMA_VERSION)
        self.assertEqual(RenderedOutput.from_dict(output.to_dict()), output)
        invalid = {**output.to_dict(), "version": "render.output.v0"}
        with self.assertRaisesRegex(ValueError, "must match"):
            RenderedOutput.from_dict(invalid)

    def test_file_created_maps_to_channel_specific_artifact_actions(self) -> None:
        expected_modes = {
            ConsoleRenderer: "artifact_reference",
            TelegramRenderer: "attachment_or_link",
            WeComRenderer: "file_message",
            WeChatRenderer: "download_link",
        }
        for renderer_type, delivery_mode in expected_modes.items():
            with self.subTest(renderer=renderer_type.__name__):
                renderer = renderer_type()
                output = renderer.render(event(StreamEventType.FILE_CREATED, 1))[0]
                self.assertEqual(output.type, RenderedOutputType.FILE)
                self.assertEqual(output.artifact.id, "art_render")
                self.assertEqual(
                    output.metadata["artifact_delivery"], delivery_mode
                )
                self.assertTrue(output.artifact.uri.startswith("artifact://"))

    def test_telegram_buffers_and_produces_throttled_updates(self) -> None:
        renderer = TelegramRenderer(min_update_chars=5)

        self.assertEqual(
            renderer.render(
                event(StreamEventType.MESSAGE_DELTA, 1, payload={"delta": "abc"})
            ),
            (),
        )
        created = renderer.render(
            event(StreamEventType.MESSAGE_DELTA, 2, payload={"delta": "def"})
        )
        self.assertEqual(created[0].type, RenderedOutputType.MESSAGE)
        self.assertEqual(created[0].text, "abcdef")

        self.assertEqual(
            renderer.render(
                event(StreamEventType.MESSAGE_DELTA, 3, payload={"delta": "gh"})
            ),
            (),
        )
        updated = renderer.flush()
        self.assertEqual(updated[0].type, RenderedOutputType.MESSAGE_UPDATE)
        self.assertEqual(updated[0].text, "abcdefgh")

    def test_wecom_segments_and_flushes_remainder(self) -> None:
        renderer = WeComRenderer(segment_chars=4)

        first = renderer.render(
            event(StreamEventType.MESSAGE_DELTA, 1, payload={"delta": "abcdef"})
        )
        remainder = renderer.flush()

        self.assertEqual([item.text for item in first], ["abcd"])
        self.assertEqual([item.text for item in remainder], ["ef"])
        self.assertTrue(
            all(item.metadata["delivery_mode"] == "segment" for item in first + remainder)
        )

    def test_wechat_buffers_until_terminal_or_explicit_flush(self) -> None:
        renderer = WeChatRenderer()
        self.assertEqual(
            renderer.render(
                event(StreamEventType.MESSAGE_DELTA, 1, payload={"delta": "缓冲"})
            ),
            (),
        )

        output = renderer.render(
            event(StreamEventType.AGENT_DONE, 2, payload={"final": "缓冲"})
        )

        self.assertEqual(output[0].type, RenderedOutputType.MESSAGE)
        self.assertEqual(output[0].text, "缓冲")
        self.assertTrue(output[0].final)

    def test_ordering_duplicate_and_close_are_enforced(self) -> None:
        renderer = ConsoleRenderer()
        first = event(StreamEventType.MESSAGE_DELTA, 1)
        renderer.render(first)

        with self.assertRaisesRegex(RenderOrderError, "unique"):
            renderer.render(
                event(StreamEventType.MESSAGE_DELTA, 2, event_id=first.event_id)
            )
        with self.assertRaisesRegex(RenderOrderError, "strictly increasing"):
            renderer.render(
                event(
                    StreamEventType.MESSAGE_DELTA,
                    1,
                    event_id="evt_out_of_order",
                )
            )

        self.assertEqual(renderer.close(), ())
        self.assertEqual(renderer.close(), ())
        with self.assertRaisesRegex(RendererClosedError, "closed"):
            renderer.render(
                event(
                    StreamEventType.MESSAGE_DELTA,
                    3,
                    event_id="evt_after_close",
                )
            )

    def test_error_event_converts_to_safe_error_output(self) -> None:
        renderer = WeChatRenderer()

        output = renderer.render(event(StreamEventType.TOOL_ERROR, 1))

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0].type, RenderedOutputType.ERROR)
        self.assertEqual(output[0].text, "测试错误")
        self.assertEqual(output[0].metadata["error_code"], "FIXTURE_ERROR")


if __name__ == "__main__":
    unittest.main()
