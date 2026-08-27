"""QwenPaw-neutral callable surface for the image_generation Tool plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import ImageGenerationRequest
from .providers.sensenova import SenseNovaConfig, SenseNovaImageProvider, SenseNovaTransport
from .registry import ImageGenerationProviderRegistry
from .service import ImageGenerationService


TOOL_NAME = "image_generation"
TOOL_DESCRIPTION = (
    "Generate a brand-new image from a text prompt when the user asks to 生成、画、"
    "创建一张图片 or generate/create/draw an image. Do not use for compressing, "
    "resizing, restoring, background removal, or upscaling an existing image."
)


def invoke_image_generation_tool(
    *,
    prompt: str,
    negative_prompt: str = "",
    width: int = 2048,
    height: int = 2048,
    seed: int | None = None,
    model: str | None = None,
    count: int = 1,
    output_dir: str | Path,
    config: SenseNovaConfig | None = None,
    transport: SenseNovaTransport | None = None,
) -> dict[str, Any]:
    registry = ImageGenerationProviderRegistry()
    registry.register(SenseNovaImageProvider(config=config, transport=transport))
    service = ImageGenerationService(registry)
    request = ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        model=model,
        count=count,
    )
    return service.generate(
        request,
        provider_name="sensenova",
        output_dir=output_dir,
    ).to_dict()
