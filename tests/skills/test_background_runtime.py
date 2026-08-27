from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from core.productivity_skills import execute_skill
from core.productivity_skills.runtime import RuntimeExecutionError


class FakeSegmentationRuntime:
    def segment(self, image, output, *, alpha_matting=False):
        with Image.open(image) as source:
            rgba = source.convert("RGBA")
            rgba.putalpha(96 if alpha_matting else 0)
            rgba.save(output, format="PNG")
            width, height = rgba.size
        return {
            "engine": "rembg",
            "model": "u2netp",
            "alpha_matting": alpha_matting,
            "width": width,
            "height": height,
        }


class BrokenSegmentationRuntime:
    def segment(self, image, output, *, alpha_matting=False):
        raise RuntimeExecutionError("fixture rembg failure")


class BackgroundRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "subject.png"
        Image.new("RGB", (12, 10), "blue").save(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def capabilities(available=True):
        return {
            "pillow": {"available": True, "status": "AVAILABLE", "mode": "native"},
            "opencv": {"available": True, "status": "AVAILABLE", "mode": "native"},
            "background_removal": {
                "available": available,
                "status": "AVAILABLE" if available else "MISSING",
                "mode": "runtime" if available else "runtime_required",
            },
        }

    def execute(self, operation, runtime=None, available=True):
        patches = [
            patch(
                "core.productivity_skills.handlers.image_tools.CapabilityResolver.resolve_many",
                return_value=self.capabilities(available),
            )
        ]
        if runtime is not None:
            patches.append(
                patch(
                    "core.productivity_skills.handlers.image_tools.get_segmentation_runtime",
                    return_value=runtime,
                )
            )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return execute_skill(
            "image-background-tools",
            {
                "operation": operation,
                "input": str(self.source),
                "output_dir": str(self.root / operation),
            },
        )

    def test_segment_uses_rembg_and_returns_alpha_artifact(self):
        response = self.execute("segment", FakeSegmentationRuntime())
        self.assertEqual(response["status"], "SUCCESS")
        self.assertEqual(response["data"]["model"], "u2netp")
        output = self.root / "segment" / response["data"]["output"]
        with Image.open(output) as rendered:
            self.assertIn("A", rendered.getbands())

    def test_alpha_matting_is_forwarded_to_adapter(self):
        response = self.execute("alpha_matting", FakeSegmentationRuntime())
        self.assertEqual(response["status"], "SUCCESS")
        self.assertTrue(response["data"]["alpha_matting"])

    def test_missing_rembg_degrades_explicitly(self):
        response = self.execute("segment", available=False)
        self.assertEqual(response["status"], "MODEL_RUNTIME_REQUIRED")

    def test_rembg_failure_is_runtime_error(self):
        response = self.execute("segment", BrokenSegmentationRuntime())
        self.assertEqual(response["status"], "RUNTIME_ERROR")
        self.assertEqual(response["error"]["code"], "RUNTIME_ERROR")


if __name__ == "__main__":
    unittest.main()
