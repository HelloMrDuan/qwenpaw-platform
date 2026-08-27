from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image

from core.image_generation.providers.sensenova import SenseNovaConfig, TransportError
from core.image_generation.tool import invoke_image_generation_tool
from tests.image_generation.support import FakeTransport, image_bytes


class ImageGenerationIdempotencyTests(unittest.TestCase):
    @staticmethod
    def _config() -> SenseNovaConfig:
        return SenseNovaConfig(api_key="test-key", max_retries=0)

    @staticmethod
    def _transport(size=(64, 36)) -> FakeTransport:
        url = "https://example.invalid/result.png"
        return FakeTransport(
            post={"data": [{"url": url}]},
            downloads={url: (image_bytes(size=size), "image/png")},
        )

    def test_19_same_tool_call_is_generated_once_and_final_size_is_exact(self) -> None:
        transport = self._transport()
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(
                prompt="1920x1080 landscape",
                requested_size="1920x1080",
                output_dir=tmp,
                config=self._config(),
                transport=transport,
                tool_call_id="call-1",
                request_id="turn-1",
            )
            first = invoke_image_generation_tool(**kwargs)
            second = invoke_image_generation_tool(**kwargs)
            with Image.open(first["images"][0]["path"]) as image:
                self.assertEqual(image.size, (1920, 1080))
        self.assertEqual(len(transport.post_calls), 1)
        self.assertFalse(first["metadata"]["idempotency_hit"])
        self.assertTrue(second["metadata"]["idempotency_hit"])
        self.assertEqual(first["final_size"], "1920x1080")

    def test_20_same_user_turn_and_payload_deduplicates_new_tool_call_id(self) -> None:
        transport = self._transport()
        with tempfile.TemporaryDirectory() as tmp:
            common = dict(
                prompt="draw a square",
                aspect_ratio="1:1",
                output_dir=tmp,
                config=self._config(),
                transport=transport,
                request_id="turn-2",
            )
            invoke_image_generation_tool(**common, tool_call_id="call-2a")
            result = invoke_image_generation_tool(**common, tool_call_id="call-2b")
        self.assertEqual(len(transport.post_calls), 1)
        self.assertTrue(result["metadata"]["idempotency_hit"])

    def test_21_different_user_turns_are_independent(self) -> None:
        transport = self._transport()
        with tempfile.TemporaryDirectory() as tmp:
            common = dict(
                prompt="draw a square",
                aspect_ratio="1:1",
                output_dir=tmp,
                config=self._config(),
                transport=transport,
            )
            invoke_image_generation_tool(**common, request_id="turn-a")
            invoke_image_generation_tool(**common, request_id="turn-b")
        self.assertEqual(len(transport.post_calls), 2)

    def test_22_non_retryable_failure_is_terminal_and_cached(self) -> None:
        transport = FakeTransport(
            post=TransportError("unauthorized", status_code=401)
        )
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(
                prompt="draw",
                output_dir=tmp,
                config=self._config(),
                transport=transport,
                request_id="turn-auth",
            )
            first = invoke_image_generation_tool(**kwargs)
            second = invoke_image_generation_tool(**kwargs)
        self.assertEqual(len(transport.post_calls), 1)
        self.assertFalse(first["retryable"])
        self.assertTrue(second["metadata"]["idempotency_hit"])

    def test_23_retryable_failure_is_not_cached(self) -> None:
        transport = FakeTransport(
            post=TransportError("temporary", status_code=503)
        )
        with tempfile.TemporaryDirectory() as tmp:
            kwargs = dict(
                prompt="draw",
                output_dir=tmp,
                config=self._config(),
                transport=transport,
                request_id="turn-retry",
            )
            first = invoke_image_generation_tool(**kwargs)
            second = invoke_image_generation_tool(**kwargs)
        self.assertEqual(len(transport.post_calls), 2)
        self.assertTrue(first["retryable"])
        self.assertFalse(second["metadata"]["idempotency_hit"])


if __name__ == "__main__":
    unittest.main()
