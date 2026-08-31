from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from core.image_generation.providers.sensenova import SenseNovaConfig
from core.image_generation.tool import invoke_image_generation_tool
from core.productivity_skills.handlers.image_tools import execute
from tests.image_generation.support import FakeTransport, image_bytes


class ImageGenerationPostprocessTests(unittest.TestCase):
    @staticmethod
    def _source(root: Path, size=(80, 60)) -> Path:
        path = root / "source.png"
        path.write_bytes(image_bytes(size=size))
        return path

    def test_exact_1080x1920_uses_portrait_bucket_and_outputs_exact_pixels(self) -> None:
        url = "https://example.invalid/portrait.png"
        transport = FakeTransport(
            post={"data": [{"url": url}]},
            downloads={url: (image_bytes(size=(36, 64)), "image/png")},
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = invoke_image_generation_tool(
                prompt="生成一张1080x1920竖版海报背景",
                requested_size="1080x1920",
                output_dir=tmp,
                config=SenseNovaConfig(api_key="test", max_retries=0),
                transport=transport,
                request_id="portrait-turn",
            )
            with Image.open(result["images"][0]["path"]) as image:
                self.assertEqual(image.size, (1080, 1920))
        self.assertEqual(transport.post_calls[0]["payload"]["size"], "1536x2752")
        self.assertEqual(result["final_size"], "1080x1920")
        self.assertEqual(len(transport.post_calls), 1)

    def test_image_toolkit_resize_path_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = execute(
                "image-toolkit",
                {
                    "operation": "resize",
                    "input": str(self._source(root)),
                    "width": 40,
                    "height": 30,
                    "output_dir": str(root / "out"),
                },
            )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["artifacts"][0]["metadata"]["width"], 40)

    def test_image_toolkit_crop_path_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = execute(
                "image-toolkit",
                {
                    "operation": "crop",
                    "input": str(self._source(root)),
                    "box": [10, 10, 50, 40],
                    "output_dir": str(root / "out"),
                },
            )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(
            (
                result["artifacts"][0]["metadata"]["width"],
                result["artifacts"][0]["metadata"]["height"],
            ),
            (40, 30),
        )

    def test_image_toolkit_fit_cover_preserves_requested_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = execute(
                "image-toolkit",
                {
                    "operation": "fit",
                    "fit_mode": "cover",
                    "input": str(self._source(root, size=(80, 80))),
                    "width": 160,
                    "height": 90,
                    "output_dir": str(root / "out"),
                },
            )
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(
            (
                result["artifacts"][0]["metadata"]["width"],
                result["artifacts"][0]["metadata"]["height"],
            ),
            (160, 90),
        )

    def test_illegal_ratio_is_structured_and_never_calls_provider(self) -> None:
        transport = FakeTransport(post={"data": []})
        with tempfile.TemporaryDirectory() as tmp:
            result = invoke_image_generation_tool(
                prompt="draw",
                aspect_ratio="21:9",
                output_dir=tmp,
                config=SenseNovaConfig(api_key="test", max_retries=0),
                transport=transport,
            )
        self.assertEqual(result["error_code"], "INVALID_IMAGE_SIZE")
        self.assertFalse(result["retryable"])
        self.assertEqual(result["supported_image_sizes"], ["1k", "2k"])
        self.assertNotIn("21:9", result["supported_aspect_ratios"])
        self.assertEqual(transport.post_calls, [])


if __name__ == "__main__":
    unittest.main()
