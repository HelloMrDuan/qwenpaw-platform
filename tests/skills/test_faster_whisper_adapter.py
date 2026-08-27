from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from core.productivity_skills.runtime import (
    FasterWhisperAdapter,
    FasterWhisperConfig,
    RuntimeExecutionError,
    registered_runtime_capabilities,
)
from core.productivity_skills.runtime.config import RuntimePaths
from core.productivity_skills.capabilities import CapabilityResolver


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.1
    no_speech_prob: float = 0.02


@dataclass
class FakeInfo:
    language: str = "zh"
    duration: float = 1.5


class FakeWhisperModel:
    def transcribe(self, media, **kwargs):
        return iter(
            [
                FakeSegment(0.0, 0.7, "你好"),
                FakeSegment(0.7, 1.5, "世界"),
            ]
        ), FakeInfo()


class FasterWhisperAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.model = self.root / "model"
        self.model.mkdir()
        (self.model / "model.bin").write_bytes(b"fixture-model")
        self.media = self.root / "zh.wav"
        with wave.open(str(self.media), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 1600)

    def tearDown(self):
        self.temporary.cleanup()

    def test_adapter_loads_configured_model_and_normalizes_chinese_segments(self):
        self.assertIn("asr", registered_runtime_capabilities())
        calls = []

        def factory(reference, **kwargs):
            calls.append((reference, kwargs))
            return FakeWhisperModel()

        config = FasterWhisperConfig(
            model="tiny",
            model_path=self.model,
            cache_dir=self.root / "cache",
            device="cpu",
            compute_type="int8",
            allow_download=False,
        )
        payload = FasterWhisperAdapter(config, model_factory=factory).transcribe(self.media)

        self.assertEqual(payload["engine"], "faster-whisper")
        self.assertEqual(payload["language"], "zh")
        self.assertEqual(payload["text"], "你好 世界")
        self.assertEqual(payload["segments"][0]["start"], 0.0)
        self.assertEqual(payload["segments"][1]["end"], 1.5)
        self.assertIn("confidence", payload["segments"][0])
        self.assertEqual(calls[0][0], str(self.model))
        self.assertTrue(calls[0][1]["local_files_only"])

    def test_model_loading_failure_is_runtime_error(self):
        config = FasterWhisperConfig(
            model="tiny",
            model_path=self.model,
            cache_dir=self.root / "cache",
            device="cpu",
            compute_type="int8",
            allow_download=False,
        )

        def broken(*args, **kwargs):
            raise ValueError("invalid model")

        with self.assertRaises(RuntimeExecutionError):
            FasterWhisperAdapter(config, model_factory=broken).load_model()

    def test_default_model_paths_are_workspace_relative_not_machine_specific(self):
        environment = {
            "QWENPAW_WORKSPACE": str(self.root),
            "QWENPAW_ASR_MODEL": "tiny",
        }
        with patch.dict(os.environ, environment, clear=True):
            paths = RuntimePaths.from_env()
            config = FasterWhisperConfig.from_env()

        self.assertEqual(paths.asr_models, self.root / ".runtime" / "models" / "asr")
        self.assertEqual(config.model, "tiny")
        source = Path(__file__).parents[2] / "core" / "productivity_skills" / "runtime"
        text = "\n".join(path.read_text(encoding="utf-8") for path in source.glob("*.py"))
        self.assertNotIn("/root/.rembg", text)
        self.assertNotIn("/run/csi", text)

    def test_capability_resolver_requires_adapter_and_accessible_model(self):
        with patch(
            "core.productivity_skills.capabilities.importlib.util.find_spec",
            return_value=object(),
        ), patch.object(
            CapabilityResolver,
            "_runtime_health",
            return_value={
                "status": "DEGRADED",
                "runtime_test": "model_missing",
                "error": "model not accessible",
            },
        ):
            capability = CapabilityResolver().resolve("asr")

        self.assertFalse(capability["available"])
        self.assertEqual(capability["status"], "DEGRADED")
        self.assertEqual(capability["mode"], "runtime_required")


if __name__ == "__main__":
    unittest.main()
