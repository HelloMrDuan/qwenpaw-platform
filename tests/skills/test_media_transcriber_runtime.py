from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from core.productivity_skills import execute_skill
from core.productivity_skills.runtime import RuntimeExecutionError


class FakeAsrRuntime:
    def transcribe(self, media, *, language=None, diarization=False):
        return {
            "language": language or "zh",
            "text": "你好 世界",
            "segments": [
                {"start": 0.0, "end": 0.8, "text": "你好"},
                {"start": 0.8, "end": 1.6, "text": "世界"},
            ],
            "engine": "faster-whisper",
            "model": "tiny",
            "duration": 1.6,
        }


class BrokenAsrRuntime:
    def transcribe(self, media, *, language=None, diarization=False):
        raise RuntimeExecutionError("fixture inference failure")


class MediaTranscriberRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media = self.root / "speech.wav"
        with wave.open(str(self.media), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\0\0" * 1600)
        self.metadata = {
            "format": {"duration": "1.6", "format_name": "wav"},
            "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le"}],
        }

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def capabilities(asr_available=True):
        return {
            "ffmpeg": {"available": True, "status": "AVAILABLE", "mode": "native"},
            "asr": {
                "available": asr_available,
                "status": "AVAILABLE" if asr_available else "MISSING",
                "mode": "runtime" if asr_available else "runtime_required",
            },
        }

    def test_transcribe_uses_adapter_and_writes_txt_markdown_srt_and_vtt(self):
        request = {
            "operation": "transcribe",
            "input": str(self.media),
            "language": "zh",
            "formats": ["txt", "markdown", "srt", "vtt"],
            "output_dir": str(self.root / "out"),
        }
        with patch(
            "core.productivity_skills.handlers.ocr_media.CapabilityResolver.resolve_many",
            return_value=self.capabilities(),
        ), patch(
            "core.productivity_skills.handlers.ocr_media._ffprobe",
            return_value=self.metadata,
        ), patch(
            "core.productivity_skills.handlers.ocr_media.get_asr_runtime",
            return_value=FakeAsrRuntime(),
        ):
            response = execute_skill("media-transcriber", request)

        self.assertEqual(response["status"], "SUCCESS")
        self.assertEqual(response["data"]["engine"], "faster-whisper")
        self.assertEqual(response["data"]["segments"][1]["end"], 1.6)
        self.assertEqual({item["metadata"]["format"] for item in response["artifacts"]}, {"txt", "markdown", "srt", "vtt"})
        srt = next(self.root.glob("out/*.srt")).read_text(encoding="utf-8")
        vtt = next(self.root.glob("out/*.vtt")).read_text(encoding="utf-8")
        self.assertIn("00:00:00,800 --> 00:00:01,600", srt)
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertIn("00:00:00.800 --> 00:00:01.600", vtt)

    def test_missing_asr_degrades_without_calling_adapter(self):
        with patch(
            "core.productivity_skills.handlers.ocr_media.CapabilityResolver.resolve_many",
            return_value=self.capabilities(False),
        ), patch(
            "core.productivity_skills.handlers.ocr_media._ffprobe",
            return_value=self.metadata,
        ), patch("core.productivity_skills.handlers.ocr_media.get_asr_runtime") as factory:
            response = execute_skill(
                "media-transcriber",
                {"operation": "transcribe", "input": str(self.media)},
            )
        self.assertEqual(response["status"], "MODEL_RUNTIME_REQUIRED")
        factory.assert_not_called()

    def test_inference_failure_is_runtime_error_not_success(self):
        with patch(
            "core.productivity_skills.handlers.ocr_media.CapabilityResolver.resolve_many",
            return_value=self.capabilities(),
        ), patch(
            "core.productivity_skills.handlers.ocr_media._ffprobe",
            return_value=self.metadata,
        ), patch(
            "core.productivity_skills.handlers.ocr_media.get_asr_runtime",
            return_value=BrokenAsrRuntime(),
        ):
            response = execute_skill(
                "media-transcriber",
                {"operation": "transcribe", "input": str(self.media)},
            )
        self.assertEqual(response["status"], "RUNTIME_ERROR")
        self.assertEqual(response["error"]["code"], "RUNTIME_ERROR")


if __name__ == "__main__":
    unittest.main()
