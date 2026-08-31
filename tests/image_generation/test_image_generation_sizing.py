from __future__ import annotations

import tempfile
import unittest

from core.image_generation.sizing import (
    SENSENOVA_SIZE_BUCKETS,
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_IMAGE_SIZES,
    UnsupportedNativeSizeError,
    infer_aspect_ratio,
    resolve_size_plan,
)
from core.image_generation.providers.sensenova import SenseNovaConfig
from core.image_generation.tool import invoke_image_generation_tool
from tests.image_generation.support import FakeTransport


class ImageGenerationSizingTests(unittest.TestCase):
    def test_01_official_image_size_values(self) -> None:
        self.assertEqual(SUPPORTED_IMAGE_SIZES, ("1k", "2k"))

    def test_02_official_aspect_ratio_values(self) -> None:
        self.assertEqual(
            SUPPORTED_ASPECT_RATIOS,
            ("2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "1:1", "16:9", "9:16", "9:21"),
        )

    def test_03_2k_landscape_maps_to_official_pixels(self) -> None:
        self.assertEqual(SENSENOVA_SIZE_BUCKETS["2k"]["16:9"], (2752, 1536))

    def test_04_1k_portrait_maps_to_official_pixels(self) -> None:
        self.assertEqual(SENSENOVA_SIZE_BUCKETS["1k"]["9:16"], (992, 1792))

    def test_05_default_is_2k_16_by_9(self) -> None:
        plan = resolve_size_plan(
            image_size=None, aspect_ratio=None, requested_size=None
        )
        self.assertEqual((plan.image_size, plan.provider_aspect_ratio), ("2k", "16:9"))
        self.assertEqual(plan.provider_size, "2752x1536")

    def test_06_landscape_intent_uses_policy_ratio(self) -> None:
        self.assertEqual(infer_aspect_ratio("请生成横屏海报", None), "16:9")

    def test_07_portrait_intent_uses_policy_ratio(self) -> None:
        self.assertEqual(infer_aspect_ratio("portrait poster", None), "9:16")

    def test_08_native_exact_size_needs_no_postprocess(self) -> None:
        plan = resolve_size_plan(
            image_size="2k",
            aspect_ratio="1:1",
            requested_size="2048x2048",
        )
        self.assertFalse(plan.postprocess_required)
        self.assertEqual(plan.provider_size, "2048x2048")

    def test_09_non_native_exact_size_uses_native_bucket_then_fit(self) -> None:
        plan = resolve_size_plan(
            image_size="2k",
            aspect_ratio="16:9",
            requested_size="1920x1080",
        )
        self.assertTrue(plan.postprocess_required)
        self.assertEqual(plan.provider_size, "2752x1536")
        self.assertEqual(plan.final_size, "1920x1080")

    def test_10_strict_native_rejects_before_provider(self) -> None:
        transport = FakeTransport(post={"data": []})
        with tempfile.TemporaryDirectory() as tmp:
            result = invoke_image_generation_tool(
                prompt="exact native only",
                image_size="2k",
                aspect_ratio="16:9",
                requested_size="1920x1080",
                require_native_size=True,
                output_dir=tmp,
                config=SenseNovaConfig(api_key="test"),
                transport=transport,
            )
        self.assertEqual(result["error_code"], "INVALID_IMAGE_SIZE")
        self.assertFalse(result["retryable"])
        self.assertEqual(result["supported_image_sizes"], ["1k", "2k"])
        self.assertIn("16:9", result["supported_aspect_ratios"])
        self.assertEqual(transport.post_calls, [])

    def test_24_square_maps_to_2048_bucket(self) -> None:
        plan = resolve_size_plan(
            image_size="2k", aspect_ratio="1:1", requested_size=None
        )
        self.assertEqual(plan.provider_size, "2048x2048")

    def test_25_portrait_maps_to_1536x2752_bucket(self) -> None:
        plan = resolve_size_plan(
            image_size="2k", aspect_ratio="9:16", requested_size=None
        )
        self.assertEqual(plan.provider_size, "1536x2752")

    def test_26_four_by_three_maps_to_official_bucket(self) -> None:
        plan = resolve_size_plan(
            image_size="2k", aspect_ratio="4:3", requested_size=None
        )
        self.assertEqual(plan.provider_size, "2368x1760")

    def test_27_three_by_four_maps_to_official_bucket(self) -> None:
        plan = resolve_size_plan(
            image_size="2k", aspect_ratio="3:4", requested_size=None
        )
        self.assertEqual(plan.provider_size, "1760x2368")

    def test_28_invalid_aspect_ratio_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_size_plan(
                image_size="2k", aspect_ratio="21:9", requested_size=None
            )


if __name__ == "__main__":
    unittest.main()
