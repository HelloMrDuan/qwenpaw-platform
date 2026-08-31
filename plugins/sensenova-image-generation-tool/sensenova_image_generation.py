"""QwenPaw-facing wrapper around the provider-neutral generation service."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import json
import os
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Literal

from core.image_generation.providers.sensenova import SenseNovaConfig
from core.image_generation.tool import TOOL_DESCRIPTION, invoke_image_generation_tool


AspectRatio = Literal[
    "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "1:1", "16:9", "9:16", "9:21"
]
ImageSize = Literal["1k", "2k"]
FitMode = Literal["cover", "contain", "stretch"]

_TOOL_CALL_ID: ContextVar[str | None] = ContextVar(
    "sensenova_image_tool_call_id", default=None
)
_REQUEST_ID: ContextVar[str | None] = ContextVar(
    "sensenova_image_request_id", default=None
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
    aspect_ratio: AspectRatio | None = None,
    image_size: ImageSize = "2k",
    requested_size: str | None = None,
    fit_mode: FitMode | None = None,
    require_native_size: bool = False,
    seed: int | None = None,
    model: str | None = None,
    count: int = 1,
):
    """Generate one image using presets instead of guessed provider pixels.

    ``requested_size`` optionally declares a final WIDTHxHEIGHT output. The
    provider receives a supported native bucket; image-toolkit performs the
    final fit when that exact size is not native.
    """

    config = _tool_config()
    result = await asyncio.to_thread(
        invoke_image_generation_tool,
        prompt=prompt,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        requested_size=requested_size,
        fit_mode=fit_mode or str(config.get("default_fit_mode") or "cover"),
        require_native_size=require_native_size,
        seed=seed,
        model=model,
        count=count,
        output_dir=_output_dir(),
        config=_provider_config(config),
        tool_call_id=_TOOL_CALL_ID.get(),
        request_id=_REQUEST_ID.get(),
        default_aspect_ratio=str(config.get("default_aspect_ratio") or "16:9"),
        landscape_aspect_ratio=str(
            config.get("landscape_aspect_ratio") or "16:9"
        ),
        portrait_aspect_ratio=str(config.get("portrait_aspect_ratio") or "9:16"),
    )
    try:
        from agentscope.message import DataBlock, TextBlock, ToolResultState, URLSource
        from agentscope.tool import ToolChunk
    except ImportError:
        return result

    metadata = dict(result.get("metadata") or {})
    if result["status"] != "SUCCESS":
        terminal = {
            "ok": False,
            "success": False,
            "status": "failed",
            "retryable": bool(result.get("retryable")),
            "error_code": result.get("error_code", "IMAGE_GENERATION_FAILED"),
            "message": result.get("error") or "Image generation failed",
            "tool_call_id": metadata.get("tool_call_id"),
            "request_id": metadata.get("request_id"),
        }
        if result.get("error_code") == "INVALID_IMAGE_SIZE":
            terminal["supported_image_sizes"] = result.get(
                "supported_image_sizes", []
            )
            terminal["supported_aspect_ratios"] = result.get(
                "supported_aspect_ratios", []
            )
        return ToolChunk(
            state=ToolResultState.ERROR,
            content=[
                TextBlock(
                    type="text",
                    text=json.dumps(terminal, ensure_ascii=False),
                )
            ],
        )

    content = []
    for image in result["images"]:
        content.append(
            DataBlock(
                source=URLSource(
                    url=Path(image["path"]).resolve().as_uri(),
                    media_type=image["mime_type"],
                )
            )
        )
    terminal = {
        "ok": True,
        "success": True,
        "status": "completed",
        "retryable": False,
        "message": (
            "Image generation completed and the image artifact is attached. "
            "Do not call image_generation again for this request."
        ),
        "provider": result["provider"],
        "model": result["model"],
        "tool_call_id": metadata.get("tool_call_id"),
        "request_id": metadata.get("request_id"),
        "idempotency_hit": metadata.get("idempotency_hit", False),
        "requested_size": result.get("requested_size"),
        "requested_aspect_ratio": result.get("requested_aspect_ratio"),
        "image_size": result.get("image_size"),
        "provider_size": result.get("provider_size"),
        "provider_aspect_ratio": result.get("provider_aspect_ratio"),
        "final_size": result.get("final_size"),
        "artifact_count": len(result["artifacts"]),
        "artifacts": result["artifacts"],
    }
    content.append(
        TextBlock(type="text", text=json.dumps(terminal, ensure_ascii=False))
    )
    return ToolChunk(state=ToolResultState.SUCCESS, content=content)


def _latest_user_request_id(agent: Any) -> str | None:
    request_context = getattr(agent, "_request_context", None) or {}
    for key in ("request_id", "qwenpaw_client_message_id"):
        value = request_context.get(key)
        if value:
            return str(value)
    state = getattr(agent, "state", None)
    context = list(getattr(state, "context", None) or [])
    for message in reversed(context):
        if str(getattr(message, "role", "")).lower() != "user":
            continue
        metadata = getattr(message, "metadata", None) or {}
        value = metadata.get("qwenpaw_client_message_id")
        if value:
            return str(value)
        value = getattr(message, "id", None)
        if value:
            return str(value)
    return None


def image_generation_middleware_factory(ctx: Any, agent_config: Any):
    """Capture official ToolCall/user-turn identifiers without core patches."""

    del ctx, agent_config
    try:
        from agentscope.middleware import MiddlewareBase
    except ImportError:
        return None

    class ImageGenerationIdentityMiddleware(MiddlewareBase):
        async def on_acting(
            self,
            agent: Any,
            input_kwargs: dict[str, Any],
            next_handler: Callable[..., AsyncGenerator[Any, None]],
        ) -> AsyncGenerator[Any, None]:
            tool_call = input_kwargs["tool_call"]
            if getattr(tool_call, "name", "") != "image_generation":
                async for item in next_handler():
                    yield item
                return
            tool_call_id = getattr(tool_call, "id", None)
            tool_token = _TOOL_CALL_ID.set(
                str(tool_call_id) if tool_call_id else None
            )
            request_token = _REQUEST_ID.set(_latest_user_request_id(agent))
            try:
                async for item in next_handler():
                    yield item
            finally:
                _REQUEST_ID.reset(request_token)
                _TOOL_CALL_ID.reset(tool_token)

    return ImageGenerationIdentityMiddleware()
