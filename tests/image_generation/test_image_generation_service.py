from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.image_generation import (
    GeneratedImage,
    GenerationStatus,
    ImageGenerationProvider,
    ImageGenerationProviderRegistry,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationService,
)

from tests.image_generation.support import image_bytes


class FakeProvider(ImageGenerationProvider):
    @property
    def name(self) -> str:
        return "fake"

    def generate(self, request, *, output_dir, progress=None):
        if progress:
            progress(GenerationStatus.SUBMITTED, "正在提交图片生成任务")
            progress(GenerationStatus.RUNNING, "正在生成图片")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "generated.png"
        path.write_bytes(image_bytes(size=(16, 12)))
        if progress:
            progress(GenerationStatus.SUCCESS, "图片生成完成")
        return ImageGenerationResponse(
            status=GenerationStatus.SUCCESS,
            images=(GeneratedImage(path, path.name, "image/png", 16, 12, request.seed),),
            provider=self.name,
            model=request.model or "fake-model",
            seed=request.seed,
            duration=0.1,
        )


class ImageGenerationServiceTests(unittest.TestCase):
    def test_registry_and_service_preserve_provider_independence(self) -> None:
        registry = ImageGenerationProviderRegistry()
        registry.register(FakeProvider())
        service = ImageGenerationService(registry)
        with tempfile.TemporaryDirectory() as tmp:
            result = service.generate(
                ImageGenerationRequest(prompt="new image", seed=9),
                provider_name="fake",
                output_dir=tmp,
            )
        self.assertEqual(result.response.status, GenerationStatus.SUCCESS)
        self.assertEqual(result.response.provider, "fake")
        self.assertEqual(
            [event.status for event in result.progress],
            [GenerationStatus.SUBMITTED, GenerationStatus.RUNNING, GenerationStatus.SUCCESS],
        )

    def test_unregistered_provider_is_explicitly_not_configured(self) -> None:
        result = ImageGenerationService(ImageGenerationProviderRegistry()).generate(
            ImageGenerationRequest(prompt="new image"),
            provider_name="missing",
            output_dir=Path("unused"),
        )
        self.assertEqual(result.response.status, GenerationStatus.PROVIDER_NOT_CONFIGURED)
        self.assertEqual(result.response.error_code, "PROVIDER_NOT_REGISTERED")


if __name__ == "__main__":
    unittest.main()
