from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.image_generation import GenerationStatus, ImageGenerationRequest
from core.image_generation.providers.sensenova import (
    SenseNovaConfig,
    SenseNovaImageProvider,
    TransportError,
)

from tests.image_generation.support import FakeTransport, IncrementingClock


class ImageGenerationErrorTests(unittest.TestCase):
    def test_missing_provider_secret_returns_provider_not_configured(self) -> None:
        transport = FakeTransport(post=AssertionError("network must not be called"))
        provider = SenseNovaImageProvider(
            config=SenseNovaConfig(api_key=""), transport=transport
        )
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="image"), output_dir=Path(tmp)
            )
        self.assertEqual(response.status, GenerationStatus.PROVIDER_NOT_CONFIGURED)
        self.assertEqual(response.error_code, "PROVIDER_NOT_CONFIGURED")
        self.assertEqual(transport.post_calls, [])

    def test_auth_failure_is_not_reported_as_success(self) -> None:
        provider = SenseNovaImageProvider(
            config=SenseNovaConfig(api_key="invalid", max_retries=0),
            transport=FakeTransport(
                post=TransportError("HTTP 401", status_code=401)
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="image"), output_dir=Path(tmp)
            )
        self.assertEqual(response.status, GenerationStatus.FAILED)
        self.assertEqual(response.error_code, "AUTH_FAILED")

    def test_async_polling_has_bounded_timeout(self) -> None:
        transport = FakeTransport(post={"task_id": "slow-task"})
        provider = SenseNovaImageProvider(
            config=SenseNovaConfig(
                api_key="test", timeout=0.5, poll_interval=0.1, max_retries=0
            ),
            transport=transport,
            sleep=lambda _: None,
            clock=IncrementingClock(step=1.0),
        )
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="image"), output_dir=Path(tmp)
            )
        self.assertEqual(response.status, GenerationStatus.TIMEOUT)
        self.assertEqual(response.error_code, "TIMEOUT")
        self.assertEqual(transport.get_calls, [])

    def test_invalid_downloaded_image_is_rejected(self) -> None:
        url = "https://example.invalid/not-image.png"
        provider = SenseNovaImageProvider(
            config=SenseNovaConfig(api_key="test", max_retries=0),
            transport=FakeTransport(
                post={"data": [{"url": url}]},
                downloads={url: (b"not an image", "image/png")},
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="image"), output_dir=Path(tmp)
            )
        self.assertEqual(response.status, GenerationStatus.FAILED)
        self.assertEqual(response.error_code, "INVALID_IMAGE")


if __name__ == "__main__":
    unittest.main()
