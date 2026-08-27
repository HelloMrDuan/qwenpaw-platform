from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.image_generation import ImageGenerationProviderRegistry, ImageGenerationRequest, ImageGenerationService
from core.image_generation.providers.sensenova import SenseNovaConfig, SenseNovaImageProvider

from tests.image_generation.support import FakeTransport, image_bytes


class ImageGenerationArtifactTests(unittest.TestCase):
    def test_successful_image_becomes_valid_artifact_with_provenance(self) -> None:
        url = "https://example.invalid/generated.png"
        transport = FakeTransport(
            post={"data": [{"url": url, "seed": 101}]},
            downloads={url: (image_bytes(size=(64, 48)), "image/png")},
        )
        registry = ImageGenerationProviderRegistry()
        registry.register(
            SenseNovaImageProvider(
                config=SenseNovaConfig(api_key="test-key", max_retries=0),
                transport=transport,
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = ImageGenerationService(registry).generate(
                ImageGenerationRequest(prompt="artifact", seed=101),
                output_dir=Path(tmp),
            )
            artifact = result.artifacts[0]
            self.assertTrue(Path(artifact.metadata["path"]).is_file())
        self.assertEqual(artifact.mime_type, "image/png")
        self.assertEqual(artifact.dimensions, {"width": 64, "height": 48})
        self.assertEqual(artifact.metadata["provider"], "sensenova")
        self.assertEqual(artifact.metadata["model"], "sensenova-u1-fast")
        self.assertEqual(artifact.metadata["seed"], 101)
        self.assertEqual(len(artifact.sha256 or ""), 64)
        self.assertTrue(artifact.uri.startswith("artifact://"))


if __name__ == "__main__":
    unittest.main()
