from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile

from core.productivity_skills import execute_skill
from core.productivity_skills.capabilities import CapabilityResolver
from scripts.build_skill_pack import build_advanced_pdf, build_skill
from scripts.generate_core_skill_scaffolds import SKILLS


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class CoreProductivitySkillPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_all_seventeen_skill_scaffolds_are_complete(self):
        self.assertEqual(len(SKILLS), 17)
        for name in SKILLS:
            root = REPOSITORY_ROOT / "skills" / name
            for relative in (
                "SKILL.md",
                "README.md",
                "skill.yaml",
                "scripts/run.py",
                "tests/README.md",
                "schemas/request.schema.json",
                "schemas/result.schema.json",
            ):
                self.assertTrue((root / relative).is_file(), f"{name}/{relative}")
            descriptor = json.loads((root / "skill.yaml").read_text(encoding="utf-8"))
            self.assertEqual(descriptor["name"], name)
            self.assertEqual(descriptor["artifact_contract"]["overwrite_source"], False)
            self.assertEqual(len(descriptor["statuses"]), 7)

    def test_capability_resolver_never_guesses_model_availability(self):
        resolver = CapabilityResolver()
        for name in ("asr", "realesrgan", "gfpgan", "codeformer", "lama", "background_removal"):
            value = resolver.resolve(name)
            self.assertIn(value["mode"], {"runtime", "runtime_required"})
            self.assertEqual(value["available"], value["mode"] == "runtime")
        self.assertEqual(resolver.resolve("not-a-capability")["mode"], "unsupported")

    def test_invalid_input_is_structured_for_every_skill(self):
        for name in SKILLS:
            response = execute_skill(name, {})
            self.assertIn(response["status"], {"INVALID_INPUT", "DEPENDENCY_MISSING"}, name)
            self.assertIsInstance(response["message"], str)
            self.assertIsInstance(response["artifacts"], list)
            self.assertIn("capabilities", response)

    def _image(self) -> Path:
        from PIL import Image
        path = self.root / "source.png"
        image = Image.new("RGB", (20, 10), (210, 190, 170))
        image.putpixel((10, 5), (20, 30, 40))
        image.save(path, dpi=(96, 96))
        return path

    def test_image_toolkit_executes_and_returns_artifact(self):
        source = self._image()
        info = execute_skill("image-toolkit", {"operation": "info", "input": str(source)})
        self.assertEqual(info["status"], "SUCCESS")
        self.assertEqual((info["data"]["width"], info["data"]["height"]), (20, 10))
        resized = execute_skill("image-toolkit", {"operation": "resize", "input": str(source), "width": 10, "output_dir": str(self.root / "out")})
        self.assertEqual(resized["status"], "SUCCESS")
        metadata = resized["artifacts"][0]["metadata"]
        self.assertEqual(metadata["width"], 10)
        self.assertEqual(metadata["height"], 5)
        for key in ("operation", "source", "output", "mime_type", "size", "checksum"):
            self.assertIn(key, metadata)
        self.assertTrue(source.is_file())

    def test_restoration_background_and_quality_traditional_fallbacks(self):
        source = self._image()
        restored = execute_skill("photo-restoration", {"input": str(source), "output_dir": str(self.root / "restore"), "gfpgan": True})
        self.assertEqual(restored["status"], "PARTIAL_SUCCESS")
        self.assertEqual(restored["error"]["code"], "MODEL_RUNTIME_REQUIRED")
        self.assertEqual(len(restored["artifacts"]), 2)
        background = execute_skill("image-background-tools", {"operation": "remove_solid", "input": str(source), "output_dir": str(self.root / "background")})
        self.assertEqual(background["status"], "SUCCESS")
        quality = execute_skill("image-quality-enhancer", {"input": str(source), "upscale": 2, "output_dir": str(self.root / "quality")})
        self.assertEqual(quality["status"], "SUCCESS")
        self.assertEqual(quality["artifacts"][0]["metadata"]["width"], 40)

    def test_missing_ocr_and_ai_runtime_are_explicit(self):
        source = self._image()
        unavailable = lambda name: {"name": name, "available": False, "mode": "runtime_required" if name in {"paddleocr", "realesrgan"} else "dependency_missing"}
        with patch.object(CapabilityResolver, "resolve", side_effect=unavailable):
            ocr = execute_skill("advanced-ocr", {"input": str(source)})
            upscale = execute_skill("image-quality-enhancer", {"input": str(source), "ai": True})
        self.assertEqual(ocr["status"], "DEPENDENCY_MISSING")
        self.assertEqual(upscale["status"], "MODEL_RUNTIME_REQUIRED")

    def test_media_summary_executes_and_asr_missing_is_explicit(self):
        media = self.root / "audio.wav"
        with wave.open(str(media), "wb") as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000); stream.writeframes(b"\0\0" * 1600)
        summary = execute_skill("media-transcriber", {"operation": "summarize_transcript", "transcript": "决定发布。行动项：张三负责回归。", "output_dir": str(self.root / "summary")})
        self.assertEqual(summary["status"], "SUCCESS")
        def capability(name):
            return {"name": name, "available": name == "ffmpeg", "mode": "native" if name == "ffmpeg" else "runtime_required"}
        with patch.object(CapabilityResolver, "resolve", side_effect=capability):
            response = execute_skill("media-transcriber", {"operation": "transcribe", "input": str(media)})
        self.assertEqual(response["status"], "MODEL_RUNTIME_REQUIRED")

    def test_sql_log_and_api_diagnostics_use_evidence(self):
        sql = execute_skill("sql-diagnostics", {"sql": "select * from users where id not in (select user_id from ban)", "error": "ORA-01427 single-row subquery", "output_dir": str(self.root)})
        self.assertEqual(sql["status"], "SUCCESS")
        self.assertEqual(sql["data"]["matched_error"]["code"], "ORA-01427")
        self.assertFalse(sql["data"]["executed"])
        logs = execute_skill("log-incident-analyzer", {"logs": ["2026-01-01 10:00:00 INFO ready", "2026-01-01 10:00:01 ERROR database refused", "2026-01-01 10:00:02 ERROR downstream failed"], "output_dir": str(self.root)})
        self.assertIn("database refused", logs["data"]["first_exception"]["message"])
        api = execute_skill("api-debugger", {"url": "https://service.invalid", "error": "connect timeout", "headers": {"Authorization": "Bearer do-not-leak"}, "output_dir": str(self.root)})
        self.assertEqual(api["data"]["classification"], "connect_failure")
        self.assertNotIn("do-not-leak", json.dumps(api))

    def test_ops_network_and_config_diagnostics_are_safe(self):
        ops = execute_skill("ops-troubleshooter", {"symptom": "pod CrashLoopBackOff", "output_dir": str(self.root)})
        self.assertFalse(ops["data"]["executed"])
        self.assertLessEqual(len(ops["data"]["verification"]), 3)
        network = execute_skill("network-diagnostics", {"host": "example.invalid", "os": "windows", "output_dir": str(self.root)})
        self.assertFalse(network["data"]["executed"])
        config = self.root / "settings.json"
        config.write_text('{"token":"real-secret-value","port":8080,"port":8081,"url":"${SERVICE_URL}"}', encoding="utf-8")
        checked = execute_skill("config-diagnostics", {"input": str(config), "output_dir": str(self.root / "config")})
        self.assertEqual(checked["status"], "SUCCESS")
        self.assertIn("port", checked["data"]["duplicate_keys"])
        self.assertNotIn("real-secret-value", json.dumps(checked))

    def test_archive_inspector_blocks_zip_slip_and_extracts_safe_archives(self):
        unsafe = self.root / "unsafe.zip"
        with zipfile.ZipFile(unsafe, "w") as package: package.writestr("../escape.txt", "blocked")
        inspected = execute_skill("archive-inspector", {"input": str(unsafe), "output_dir": str(self.root / "inspect")})
        self.assertEqual(inspected["data"]["unsafe_paths"], ["../escape.txt"])
        blocked = execute_skill("archive-inspector", {"operation": "extract", "input": str(unsafe), "output_dir": str(self.root / "extract")})
        self.assertEqual(blocked["status"], "INVALID_INPUT")
        self.assertEqual(blocked["error"]["code"], "PATH_TRAVERSAL")

    def test_data_profiler_and_document_batch_processor(self):
        dataset = self.root / "data.csv"
        dataset.write_text("id,label,value\n1,A,10\n2,A,12\n2,A,12\n3,B,100\n", encoding="utf-8")
        profile = execute_skill("data-profiler", {"input": str(dataset), "label_column": "label", "output_dir": str(self.root / "profile")})
        self.assertEqual(profile["status"], "SUCCESS")
        self.assertEqual(profile["data"]["rows"], 4)
        self.assertEqual(profile["data"]["duplicate_rows"], 1)
        documents = self.root / "documents"; documents.mkdir(); (documents / "a.docx").write_bytes(b"doc"); (documents / "b.pdf").write_bytes(b"pdf")
        batch = execute_skill("document-batch-processor", {"input": str(documents), "output_dir": str(self.root / "batch")})
        self.assertEqual(batch["status"], "SUCCESS")
        delegates = {item["delegate_skill"] for item in batch["data"]["plan"]}
        self.assertEqual(delegates, {"docx", "pdf"})

    def test_release_notes_and_research_reports(self):
        notes = execute_skill("release-notes", {"git_log": "feat(api): add endpoint\nfix(db): handle null\nrefactor!: remove legacy", "changed_files": ["db/migration/V2.sql", "config/app.yml", "tests/test_api.py"], "output_dir": str(self.root / "release")})
        self.assertEqual(notes["status"], "SUCCESS")
        self.assertEqual(len(notes["data"]["breaking_changes"]), 1)
        research = execute_skill("web-research-report", {"question": "Is X supported?", "sources": [{"title": "Official A", "url": "https://example.com/a", "authority": "official", "published": "2026-01-01", "claims": ["X is supported"]}, {"title": "Paper B", "url": "https://example.com/b", "authority": "research", "published": "2026-02-01", "claims": ["X is supported"]}], "inferences": ["Adoption may increase"], "output_dir": str(self.root / "research")})
        self.assertEqual(research["status"], "SUCCESS")
        self.assertEqual(len(research["data"]["corroborated_claims"]), 1)
        self.assertFalse(research["data"]["browser_access_performed"])

    def test_all_skill_zips_are_isolated_and_integrity_checked(self):
        output = self.root / "dist"
        base_python = Path(getattr(sys, "_base_executable", sys.executable))
        for name in SKILLS:
            built = build_skill(REPOSITORY_ROOT, output, name)
            archive = Path(built.archive)
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), built.sha256)
            extraction = self.root / "installed" / name
            with zipfile.ZipFile(archive) as package:
                self.assertIsNone(package.testzip())
                package.extractall(extraction)
                self.assertIn("SKILL.md", package.namelist())
                self.assertFalse(any("__pycache__" in item or item.endswith((".pt", ".pth", ".onnx")) for item in package.namelist()))
            completed = subprocess.run([str(base_python), "-I", str(extraction / "scripts" / "run.py"), "--request", "{}"], cwd=extraction, capture_output=True, text=True, timeout=30, check=False)
            payload = json.loads(completed.stdout)
            self.assertIn(payload["status"], {"INVALID_INPUT", "DEPENDENCY_MISSING"}, name)
            self.assertNotIn(str(REPOSITORY_ROOT), completed.stdout + completed.stderr)

    def test_advanced_pdf_editor_release_alias_is_preserved(self):
        built = build_advanced_pdf(REPOSITORY_ROOT, self.root / "dist")
        self.assertEqual(Path(built.archive).name, "advanced-pdf-editor.skill.zip")
        with zipfile.ZipFile(built.archive) as package:
            self.assertIn("SKILL.md", package.namelist())
            self.assertIn("scripts/pdf_editor.py", package.namelist())


if __name__ == "__main__":
    unittest.main()
