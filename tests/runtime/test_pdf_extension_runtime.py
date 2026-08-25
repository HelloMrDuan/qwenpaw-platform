from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from core.contracts import Artifact, ArtifactKind, SkillRequest
from core.extensions import ExtensionRegistry, ExtensionType
from core.extensions.runtime import SkillInvoker, UnsupportedSkillExecutor
from core.streaming import StreamCollector, StreamingBridge


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "pdf-editor"


class PDFExtensionRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ExtensionRegistry(REPOSITORY_ROOT)
        self.discovered = self.registry.discover()
        self.invoker = SkillInvoker(REPOSITORY_ROOT, self.registry)

    def test_pdf_manifest_executor_events_and_artifact_end_to_end(self) -> None:
        metadata = self.registry.get("pdf-editor")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertIn(metadata, self.discovered)
        self.assertEqual(metadata.type, ExtensionType.SKILL)
        self.assertEqual(metadata.executor["path"], "executor/main.py")
        self.assertEqual(metadata.executor["callable"], "execute")

        descriptor = self.invoker.describe("pdf-editor")
        self.assertEqual(descriptor.name, "pdf-editor")
        self.assertEqual(descriptor.executor_path, SKILL_ROOT / "executor" / "main.py")

        fixture = SKILL_ROOT / "tests" / "fixtures" / "native_three_pages.pdf"
        source_digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        engine = SKILL_ROOT / "scripts" / "pdf_editor.py"
        engine_digest_before = hashlib.sha256(engine.read_bytes()).hexdigest()
        source = Artifact(
            id="source_pdf_runtime",
            kind=ArtifactKind.FILE,
            name=fixture.name,
            mime_type="application/pdf",
            size_bytes=fixture.stat().st_size,
            uri="artifact://fixtures/native_three_pages.pdf",
            sha256=source_digest,
        )
        request = SkillRequest(
            request_id="req_pdf_extension_runtime",
            skill_id="pdf-editor",
            files=(source,),
            parameters={
                "command": "apply",
                "output_name": "runtime-bridge-output.pdf",
                "plan": {
                    "operations": [
                        {
                            "action": "add_text",
                            "page": 1,
                            "text": "Extension Runtime Bridge",
                            "x": 72,
                            "y": 120,
                            "font_size": 12,
                        }
                    ]
                },
            },
            context={
                "stream_id": "str_pdf_extension_runtime",
                "trace_id": "trc_pdf_extension_runtime",
                "session_id": "ses_pdf_extension_runtime",
                "conversation_id": "conv_pdf_extension_runtime",
                "task_id": "task_pdf_extension_runtime",
                "tool_call_id": "call_pdf_extension_runtime",
            },
        )

        streaming = StreamingBridge()
        collector = StreamCollector()
        streaming.subscribe(collector)
        with tempfile.TemporaryDirectory(prefix="pdf-extension-runtime-") as directory:
            output_directory = Path(directory)

            def publish_artifact(path: Path) -> Artifact:
                target = output_directory / path.name
                shutil.copy2(path, target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                return Artifact(
                    id="art_pdf_extension_runtime",
                    kind=ArtifactKind.FILE,
                    name=target.name,
                    mime_type="application/pdf",
                    size_bytes=target.stat().st_size,
                    uri=f"artifact://outputs/{target.name}",
                    sha256=digest,
                )

            runtime_result = self.invoker.invoke(
                request,
                resolve_artifact=lambda artifact: fixture,
                publish_artifact=publish_artifact,
                event_publisher=streaming,
                python_executable=sys.executable,
            )

            self.assertTrue(runtime_result.result.success)
            self.assertEqual(runtime_result.published_event_count, len(runtime_result.events))
            self.assertEqual(len(runtime_result.artifacts), 1)
            artifact = runtime_result.artifacts[0]
            output = output_directory / artifact.name
            self.assertTrue(output.is_file())
            self.assertEqual(artifact.mime_type, "application/pdf")
            self.assertEqual(artifact.sha256, hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertNotEqual(artifact.sha256, source_digest)

        event_names = [event.event.value for event in collector.events]
        self.assertEqual(event_names[0], "tool.start")
        self.assertIn("tool.progress", event_names)
        self.assertEqual(event_names[-2:], ["file.created", "tool.result"])
        self.assertEqual(tuple(collector.events), runtime_result.events)
        self.assertEqual(
            streaming.replay("ses_pdf_extension_runtime"), runtime_result.events
        )
        self.assertEqual(
            hashlib.sha256(engine.read_bytes()).hexdigest(), engine_digest_before
        )
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), source_digest)

    def test_runtime_bridge_rejects_every_non_pdf_skill(self) -> None:
        with self.assertRaisesRegex(UnsupportedSkillExecutor, "only permits"):
            self.invoker.describe("some-other-skill")


if __name__ == "__main__":
    unittest.main()
