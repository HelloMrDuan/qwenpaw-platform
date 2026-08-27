"""Offline routing-contract tests for generation versus image processing.

These tests protect the published Skill descriptions used by QwenPaw routing.
They do not claim to execute the unavailable cloud QwenPaw router locally.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROCESSING_SKILLS = (
    "image-toolkit",
    "photo-restoration",
    "image-background-tools",
    "image-quality-enhancer",
)


def expected_capability(prompt: str) -> str:
    """Express the accepted intent boundary without implementing a router."""

    if "生成一张" in prompt or "根据文字生成" in prompt:
        return "image-generation-capability"
    if "老照片" in prompt and ("修复" in prompt or "恢复" in prompt):
        return "photo-restoration"
    if "背景" in prompt and any(word in prompt for word in ("去掉", "移除", "删除", "透明")):
        return "image-background-tools"
    if any(word in prompt for word in ("缩小", "调整尺寸", "裁剪", "旋转")):
        return "image-toolkit"
    if any(word in prompt for word in ("放大2倍", "放大4倍", "2x", "4x")):
        return "image-quality-enhancer"
    return "unclassified"


class ImageGenerationRoutingBoundaryTests(unittest.TestCase):
    def test_text_to_image_uses_reserved_generation_capability(self) -> None:
        route = expected_capability("生成一张赛博朋克城市图片")
        self.assertEqual(route, "image-generation-capability")
        self.assertNotIn(route, PROCESSING_SKILLS)

    def test_resize_uses_image_toolkit(self) -> None:
        self.assertEqual(expected_capability("把这张图缩小到 512x512"), "image-toolkit")

    def test_old_photo_uses_photo_restoration(self) -> None:
        self.assertEqual(expected_capability("把这张老照片修复一下"), "photo-restoration")

    def test_background_removal_uses_background_tools(self) -> None:
        self.assertEqual(expected_capability("把人物背景去掉"), "image-background-tools")

    def test_upscale_uses_quality_enhancer(self) -> None:
        self.assertEqual(expected_capability("把这张图放大2倍"), "image-quality-enhancer")

    def test_processing_skill_metadata_requires_existing_image(self) -> None:
        for skill_name in PROCESSING_SKILLS:
            with self.subTest(skill=skill_name):
                root = REPOSITORY_ROOT / "skills" / skill_name
                descriptor = json.loads((root / "skill.yaml").read_text(encoding="utf-8"))
                skill_doc = (root / "SKILL.md").read_text(encoding="utf-8")
                description = descriptor["description"]
                self.assertIn("existing input image", description)
                self.assertIn("Never use for text-to-image", description)
                self.assertIn(f'description: "{description}"', skill_doc)
                self.assertIn("## Routing boundary", skill_doc)

    def test_current_builtin_registry_has_no_image_generator(self) -> None:
        config = json.loads(
            (REPOSITORY_ROOT / "configs" / "agent.json").read_text(encoding="utf-8")
        )
        tool_names = set(config["tools"]["builtin_tools"])
        self.assertTrue({"view_image", "send_file_to_user"}.issubset(tool_names))
        self.assertTrue(
            {"image_generate", "image_generation", "generate_image"}.isdisjoint(tool_names)
        )


if __name__ == "__main__":
    unittest.main()
