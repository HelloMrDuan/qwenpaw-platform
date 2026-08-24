from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
for path in (REPO_ROOT, SKILL_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.contracts import Artifact, ArtifactKind, SkillRequest
from executor.main import execute
from helpers import FIXTURES


class PDFEditorContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pdf-editor-v12-contract-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def artifact(self, path: Path, artifact_id: str, kind: ArtifactKind) -> Artifact:
        return Artifact(
            id=artifact_id,
            kind=kind,
            name=path.name,
            mime_type="application/pdf" if path.suffix == ".pdf" else "image/png",
            size_bytes=path.stat().st_size,
            uri=f"artifact://fixtures/{path.name}",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )

    def test_request_and_result_schemas_are_versioned(self) -> None:
        request = json.loads((SKILL_ROOT / "schemas" / "request.schema.json").read_text(encoding="utf-8"))
        result = json.loads((SKILL_ROOT / "schemas" / "result.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(request["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("plan", request["properties"]["parameters"]["required"])
        self.assertEqual(result["properties"]["events"]["items"]["properties"]["schema_version"]["const"], "stream.v1")
        self.assertTrue(
            {"status", "message", "artifacts", "events", "validation"}.issubset(
                set(result["required"])
            )
        )

    def test_skill_request_executes_engine_and_returns_validated_artifact(self) -> None:
        source_path = FIXTURES / "native_three_pages.pdf"
        source = self.artifact(source_path, "source_pdf", ArtifactKind.FILE)
        mapping = {source.id: source_path}

        def resolve(artifact: Artifact) -> Path:
            return mapping[artifact.id]

        def publish(path: Path) -> Artifact:
            target = self.output / path.name
            shutil.copy2(path, target)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            return Artifact(
                id="output_pdf",
                kind=ArtifactKind.FILE,
                name=target.name,
                mime_type="application/pdf",
                size_bytes=target.stat().st_size,
                uri="artifact://outputs/output.pdf",
                sha256=digest,
            )

        request = SkillRequest(
            request_id="req_contract_success",
            skill_id="pdf-editor",
            files=(source,),
            parameters={
                "command": "apply",
                "output_name": "contract-output.pdf",
                "plan": {
                    "operations": [
                        {"action": "insert_pages", "at": 2, "count": 1}
                    ]
                },
            },
            context={
                "trace_id": "trc_contract",
                "session_id": "ses_contract",
                "conversation_id": "conv_contract",
                "task_id": "task_contract",
                "stream_id": "str_contract",
                "tool_call_id": "call_contract",
            },
        )
        result = execute(request, resolve_artifact=resolve, publish_artifact=publish)

        self.assertTrue(result.success)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.artifacts[0].uri, "artifact://outputs/output.pdf")
        self.assertTrue(result.validation["reopen_ok"])
        event_names = [event.event.value for event in result.events]
        self.assertEqual(event_names[0], "tool.start")
        self.assertIn("tool.progress", event_names)
        self.assertEqual(event_names[-2:], ["file.created", "tool.result"])
        self.assertEqual([event.sequence for event in result.events], list(range(1, len(result.events) + 1)))
        json.dumps(result.to_dict(), ensure_ascii=False)

    def test_contract_failure_returns_tool_error_without_artifact(self) -> None:
        source_path = FIXTURES / "native_three_pages.pdf"
        source = self.artifact(source_path, "source_pdf", ArtifactKind.FILE)
        request = SkillRequest(
            request_id="req_contract_failure",
            skill_id="pdf-editor",
            files=(source,),
            parameters={"plan": {"operations": [{"action": "unsupported"}]}},
            context={},
        )
        result = execute(
            request,
            resolve_artifact=lambda artifact: source_path,
            publish_artifact=lambda path: self.fail("publisher must not be called"),
        )
        self.assertFalse(result.success)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.artifacts, ())
        self.assertEqual(result.events[-1].event.value, "tool.error")


if __name__ == "__main__":
    unittest.main()
