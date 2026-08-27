"""QwenPaw-facing wrapper around the provider-neutral generation service."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from core.image_generation.providers.sensenova import SenseNovaConfig
from core.image_generation.tool import (
    TOOL_DESCRIPTION,
    invoke_image_generation_tool,
)


def _tool_config() -> dict[str, Any]:
    try:
        from qwenpaw.plugins import get_tool_config
    except ImportError:
        return {}
    config = get_tool_config("image_generation")
    return dict(config) if config else {}


def _provider_config(config: dict[str, Any]) -> SenseNovaConfig:
    env = SenseNovaConfig.from_env()
    return SenseNovaConfig(
        api_key=str(config.get("api_key") or env.api_key),
        base_url=str(config.get("base_url") or env.base_url),
        model=str(config.get("model") or env.model),
        timeout=float(config.get("timeout") or env.timeout),
        poll_interval=float(config.get("poll_interval") or env.poll_interval),
        max_retries=env.max_retries,
        status_url_template=env.status_url_template,
    )


def _output_dir() -> Path:
    configured = os.environ.get("QWENPAW_IMAGE_GENERATION_ARTIFACT_DIR")
    if configured:
        return Path(configured).expanduser()
    try:
        from qwenpaw.constant import DEFAULT_MEDIA_DIR
    except ImportError:
        return Path.cwd() / "artifacts" / "image_generation"
    return Path(DEFAULT_MEDIA_DIR) / "sensenova_image_generation"


async def image_generation(
    prompt: str,
    negative_prompt: str = "",
    width: int = 2048,
    height: int = 2048,
    seed: int | None = None,
    model: str | None = None,
    count: int = 1,
):
    """Generate a new image from text; never use for editing an existing image."""

    result = await asyncio.to_thread(
        invoke_image_generation_tool,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        model=model,
        count=count,
        output_dir=_output_dir(),
        config=_provider_config(_tool_config()),
    )
    try:
        from agentscope.message import DataBlock, TextBlock, ToolResultState, URLSource
        from agentscope.tool import ToolChunk
    except ImportError:
        return result

    if result["status"] != "SUCCESS":
        message = result.get("error") or "Image generation failed"
        return ToolChunk(
            state=ToolResultState.ERROR,
            content=[TextBlock(type="text", text=f"{result['status']}: {message}")],
        )
    content = []
    for image in result["images"]:
        content.append(
            DataBlock(
                source=URLSource(
                    url="file://" + image["path"],
                    media_type=image["mime_type"],
                )
            )
        )
    content.append(
        TextBlock(
            type="text",
            text=json.dumps(
                {
                    "status": result["status"],
                    "provider": result["provider"],
                    "model": result["model"],
                    "artifacts": result["artifacts"],
                },
                ensure_ascii=False,
            ),
        )
    )
    return ToolChunk(state=ToolResultState.SUCCESS, content=content)
