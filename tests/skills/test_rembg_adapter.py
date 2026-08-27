from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from core.productivity_skills.runtime import (
    RembgAdapter,
    RembgConfig,
    registered_runtime_capabilities,
)


class RembgAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.models = self.root / "models"
        self.models.mkdir()
        (self.models / "u2netp.onnx").write_bytes(b"fixture-model")
        self.source = self.root / "subject.png"
        Image.new("RGB", (8, 6), "red").save(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def test_u2netp_session_and_remove_produce_png_alpha(self):
        self.assertIn("background_removal", registered_runtime_capabilities())
        session_calls = []
        remove_calls = []

        def session_factory(model, **kwargs):
            session_calls.append((model, kwargs))
            return object()

        def remove(content, **kwargs):
            remove_calls.append(kwargs)
            with Image.open(BytesIO(content)) as image:
                rgba = image.convert("RGBA")
                rgba.putalpha(128)
                output = BytesIO()
                rgba.save(output, format="PNG")
                return output.getvalue()

        config = RembgConfig("u2netp", self.models, False)
        output = self.root / "out.png"
        payload = RembgAdapter(
            config,
            session_factory=session_factory,
            remove_function=remove,
        ).segment(self.source, output, alpha_matting=True)

        self.assertEqual(payload["engine"], "rembg")
        self.assertEqual(payload["model"], "u2netp")
        self.assertTrue(payload["alpha_matting"])
        self.assertEqual(session_calls[0][0], "u2netp")
        self.assertEqual(Path(session_calls[0][1]["u2net_home"]), self.models)
        self.assertTrue(remove_calls[0]["alpha_matting"])
        with Image.open(output) as rendered:
            self.assertIn("A", rendered.getbands())

    def test_default_is_small_u2netp_and_large_bria_is_rejected(self):
        with patch.dict("os.environ", {"QWENPAW_REMBG_MODEL_DIR": str(self.models)}, clear=True):
            self.assertEqual(RembgConfig.from_env().model, "u2netp")
            with self.assertRaises(Exception):
                RembgConfig.from_env({"model": "bria-rmbg-2.0"})


if __name__ == "__main__":
    unittest.main()
