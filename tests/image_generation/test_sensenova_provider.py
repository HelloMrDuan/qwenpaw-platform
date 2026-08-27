from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.image_generation import GenerationStatus, ImageGenerationRequest
from core.image_generation.providers.sensenova import SenseNovaConfig, SenseNovaImageProvider

from tests.image_generation.support import FakeTransport, image_bytes


class SenseNovaProviderTests(unittest.TestCase):
    def config(self, **overrides) -> SenseNovaConfig:
        values = {
            "api_key": "test-only-key",
            "base_url": "https://token.sensenova.cn/v1",
            "model": "sensenova-u1-fast",
            "timeout": 10,
            "poll_interval": 0.01,
            "max_retries": 0,
        }
        values.update(overrides)
        return SenseNovaConfig(**values)

    def test_sync_generation_uses_recovered_protocol_and_downloads_image(self) -> None:
        url = "https://example.invalid/result.png"
        transport = FakeTransport(
            post={"data": [{"url": url, "seed": 42}]},
            downloads={url: (image_bytes(), "image/png")},
        )
        provider = SenseNovaImageProvider(config=self.config(), transport=transport)
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(
                    prompt="industrial control room",
                    negative_prompt="blurry",
                    width=2048,
                    height=2048,
                    seed=42,
                ),
                output_dir=Path(tmp),
            )
        self.assertEqual(response.status, GenerationStatus.SUCCESS)
        self.assertEqual(response.images[0].mime_type, "image/png")
        call = transport.post_calls[0]
        self.assertEqual(call["url"], "https://token.sensenova.cn/v1/images/generations")
        self.assertEqual(call["payload"]["model"], "sensenova-u1-fast")
        self.assertEqual(call["payload"]["size"], "2048x2048")
        self.assertEqual(call["payload"]["negative_prompt"], "blurry")
        self.assertEqual(call["headers"]["Authorization"], "Bearer test-only-key")

    def test_async_task_is_polled_until_success(self) -> None:
        url = "https://example.invalid/async.jpg"
        transport = FakeTransport(
            post={"task_id": "task-1", "status": "SUBMITTED"},
            polls=[
                {"task_id": "task-1", "status": "RUNNING"},
                {"task_id": "task-1", "status": "SUCCESS", "images": [{"raw": url}]},
            ],
            downloads={url: (image_bytes("JPEG"), "image/jpeg")},
        )
        provider = SenseNovaImageProvider(
            config=self.config(), transport=transport, sleep=lambda _: None, clock=lambda: 0.0
        )
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="city"), output_dir=Path(tmp)
            )
        self.assertEqual(response.status, GenerationStatus.SUCCESS)
        self.assertEqual(response.task_id, "task-1")
        self.assertEqual(len(transport.get_calls), 2)
        self.assertTrue(transport.get_calls[0]["url"].endswith("/images/generations/task-1"))

    def test_multi_image_response_materializes_every_requested_image(self) -> None:
        first = "https://example.invalid/1.png"
        second = "https://example.invalid/2.png"
        transport = FakeTransport(
            post={"data": [{"url": first, "seed": 7}, {"url": second, "seed": 8}]},
            downloads={
                first: (image_bytes(size=(20, 10)), "image/png"),
                second: (image_bytes(size=(30, 15)), "image/png"),
            },
        )
        provider = SenseNovaImageProvider(config=self.config(), transport=transport)
        with tempfile.TemporaryDirectory() as tmp:
            response = provider.generate(
                ImageGenerationRequest(prompt="two views", count=2), output_dir=Path(tmp)
            )
            self.assertTrue(all(image.path.is_file() for image in response.images))
        self.assertEqual(len(response.images), 2)
        self.assertEqual([image.seed for image in response.images], [7, 8])


if __name__ == "__main__":
    unittest.main()
