from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.productivity_skills import execute_skill
from core.productivity_skills.capabilities import CapabilityResolver


class ImageQualityStatusSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        from PIL import Image

        self.source = self.root / "source.png"
        Image.new("RGB", (16, 8), (120, 130, 140)).save(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def test_requested_2x_but_actual_1x_is_never_success(self):
        def keep_original_size(image, _size, *args, **kwargs):
            return image.copy()

        with patch("PIL.Image.Image.resize", autospec=True, side_effect=keep_original_size):
            response = execute_skill(
                "image-quality-enhancer",
                {
                    "operation": "upscale_2x",
                    "input": str(self.source),
                    "output_dir": str(self.root / "out"),
                },
            )

        self.assertEqual(response["status"], "PARTIAL_SUCCESS")
        self.assertNotEqual(response["status"], "SUCCESS")
        self.assertEqual(response["data"]["requested_scale"], 2)
        self.assertEqual(response["data"]["actual_scale"], 1)
        self.assertEqual(response["data"]["mode"], "traditional")
        self.assertEqual(response["data"]["missing_capability"], "realesrgan")

    def test_requested_4x_ai_without_runtime_is_explicit(self):
        unavailable = {
            "name": "realesrgan",
            "available": False,
            "mode": "runtime_required",
        }
        with patch.object(CapabilityResolver, "resolve", return_value=unavailable):
            response = execute_skill(
                "image-quality-enhancer",
                {
                    "operation": "upscale_4x",
                    "input": str(self.source),
                    "ai": True,
                },
            )

        self.assertEqual(response["status"], "MODEL_RUNTIME_REQUIRED")
        self.assertEqual(response["data"]["requested_scale"], 4)
        self.assertEqual(response["data"]["actual_scale"], 1)
        self.assertEqual(response["data"]["missing_capability"], "realesrgan")


if __name__ == "__main__":
    unittest.main()
