from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "pdf-editor"
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from core.contracts import Artifact, ArtifactKind, SkillRequest  # noqa: E402
from core.streaming import StreamCollector, StreamingBridge  # noqa: E402
from executor.main import execute  # noqa: E402


class PDFEditorStreamingBridgeTests(unittest.TestCase):
    def test_pdf_editor_events_are_consumed_in_order_and_replayed(self) -> None:
        fixture = SKILL_ROOT / "tests" / "fixtures" / "native_three_pages.pdf"
        source = Artifact(
            id="source_pdf_bridge",
            kind=ArtifactKind.FILE,
            name=fixture.name,
            mime_type="application/pdf",
            size_bytes=fixture.stat().st_size,
            uri="artifact://fixtures/native_three_pages.pdf",
            sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        )
        request = SkillRequest(
            request_id="req_pdf_stream_bridge",
            skill_id="pdf-editor",
            files=(source,),
            parameters={
                "command": "apply",
                "output_name": "stream-bridge-output.pdf",
                "plan": {
                    "operations": [
                        {
                            "action": "add_text",
                            "page": 1,
                            "text": "Streaming Bridge",
                            "x": 72,
                            "y": 120,
                            "font_size": 12,
                        }
                    ]
                },
            },
            context={
                "stream_id": "str_pdf_bridge",
                "trace_id": "trc_pdf_bridge",
                "session_id": "ses_pdf_bridge",
                "conversation_id": "conv_pdf_bridge",
                "task_id": "task_pdf_bridge",
                "tool_call_id": "call_pdf_bridge",
            },
        )

        with tempfile.TemporaryDirectory(prefix="pdf-stream-bridge-") as directory:
            output_dir = Path(directory)

            def publish_artifact(path: Path) -> Artifact:
                target = output_dir / path.name
                shutil.copy2(path, target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                return Artifact(
                    id="art_pdf_bridge",
                    kind=ArtifactKind.FILE,
                    name=target.name,
                    mime_type="application/pdf",
                    size_bytes=target.stat().st_size,
                    uri="artifact://outputs/stream-bridge-output.pdf",
                    sha256=digest,
                )

            result = execute(
                request,
                resolve_artifact=lambda artifact: fixture,
                publish_artifact=publish_artifact,
            )

        self.assertTrue(result.success)
        bridge = StreamingBridge()
        collector = StreamCollector()
        bridge.subscribe(collector)
        for event in result.events:
            bridge.publish(event)

        event_names = [event.event.value for event in collector.events]
        self.assertEqual(event_names[0], "tool.start")
        self.assertIn("tool.progress", event_names)
        self.assertEqual(event_names[-2:], ["file.created", "tool.result"])
        self.assertEqual(
            [event.sequence for event in collector.events],
            list(range(1, len(collector.events) + 1)),
        )
        self.assertEqual(
            len({event.event_id for event in collector.events}),
            len(collector.events),
        )
        self.assertEqual(
            {event.session_id for event in collector.events}, {"ses_pdf_bridge"}
        )
        self.assertEqual(bridge.replay("ses_pdf_bridge"), result.events)


if __name__ == "__main__":
    unittest.main()
