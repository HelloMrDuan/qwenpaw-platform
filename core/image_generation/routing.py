"""Explicit intent boundary between new-image generation and image processing."""

from __future__ import annotations


def route_image_request(prompt: str, *, has_input_image: bool = False) -> str:
    """Return the capability reserved by the published routing contract."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be non-empty text")
    text = prompt.strip().lower()
    if not has_input_image and any(
        phrase in text
        for phrase in (
            "生成一张",
            "画一张",
            "创建一张图片",
            "根据描述生成图片",
            "generate an image",
            "create an image",
            "draw an image",
        )
    ):
        return "image_generation"
    if any(phrase in text for phrase in ("老照片", "old photo")) and any(
        word in text for word in ("修复", "恢复", "restore")
    ):
        return "photo-restoration"
    if "背景" in text and any(word in text for word in ("去掉", "移除", "删除", "透明")):
        return "image-background-tools"
    if any(word in text for word in ("放大2倍", "放大4倍", "upscale 2x", "upscale 4x")):
        return "image-quality-enhancer"
    if any(word in text for word in ("压缩", "缩小", "调整尺寸", "裁剪", "旋转", "compress")):
        return "image-toolkit"
    return "unclassified"
