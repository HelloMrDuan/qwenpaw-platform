"""QwenPaw-neutral callable surface for the image_generation Tool plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import ImageGenerationRequest
from .idempotency import ImageGenerationIdempotencyStore
from .providers.sensenova import SenseNovaConfig, SenseNovaImageProvider, SenseNovaTransport
from .registry import ImageGenerationProviderRegistry
from .service import ImageGenerationService
from .sizing import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_IMAGE_SIZE,
    DEFAULT_LANDSCAPE_ASPECT_RATIO,
    DEFAULT_PORTRAIT_ASPECT_RATIO,
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_IMAGE_SIZES,
    UnsupportedNativeSizeError,
    infer_aspect_ratio,
    infer_requested_size,
)


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
    aspect_ratio: str | None = None,
    image_size: str = DEFAULT_IMAGE_SIZE,
    requested_size: str | None = None,
    fit_mode: str = "cover",
    require_native_size: bool = False,
    seed: int | None = None,
    model: str | None = None,
    count: int = 1,
    output_dir: str | Path,
    config: SenseNovaConfig | None = None,
    transport: SenseNovaTransport | None = None,
    tool_call_id: str | None = None,
    request_id: str | None = None,
    default_aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    landscape_aspect_ratio: str = DEFAULT_LANDSCAPE_ASPECT_RATIO,
    portrait_aspect_ratio: str = DEFAULT_PORTRAIT_ASPECT_RATIO,
    idempotency_store: ImageGenerationIdempotencyStore | None = None,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    try:
        resolved_ratio = infer_aspect_ratio(
            prompt,
            aspect_ratio,
            default_aspect_ratio=default_aspect_ratio,
            landscape_aspect_ratio=landscape_aspect_ratio,
            portrait_aspect_ratio=portrait_aspect_ratio,
        )
        resolved_requested_size = infer_requested_size(prompt, requested_size)
        request = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=resolved_ratio,
            image_size=image_size,
            requested_size=resolved_requested_size,
            fit_mode=fit_mode,
            require_native_size=require_native_size,
            seed=seed,
            model=model,
            count=count,
        )
    except (TypeError, ValueError, UnsupportedNativeSizeError) as exc:
        detail = str(exc)
        size_error = isinstance(exc, UnsupportedNativeSizeError) or any(
            field in detail
            for field in (
                "image_size",
                "aspect_ratio",
                "requested_size",
                "native SenseNova size",
                "fit_mode",
            )
        )
        return {
            "status": "FAILED",
            "images": [],
            "artifacts": [],
            "progress": [],
            "metadata": {
                "capability": "image_generation",
                "tool_call_id": tool_call_id,
                "request_id": request_id,
                "idempotency_hit": False,
            },
            "retryable": False,
            "error": detail,
            "error_code": "INVALID_IMAGE_SIZE" if size_error else "INVALID_ARGUMENT",
            **(
                {
                    "supported_image_sizes": list(SUPPORTED_IMAGE_SIZES),
                    "supported_aspect_ratios": list(SUPPORTED_ASPECT_RATIOS),
                }
                if size_error
                else {}
            ),
        }

    request_payload = {
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "aspect_ratio": request.aspect_ratio,
        "image_size": request.image_size,
        "requested_size": request.requested_size,
        "fit_mode": request.fit_mode,
        "require_native_size": request.require_native_size,
        "seed": request.seed,
        "model": request.model,
        "count": request.count,
    }
    store = idempotency_store or ImageGenerationIdempotencyStore(
        output_root / ".image_generation_idempotency"
    )
    fingerprint = store.fingerprint(request_payload)
    keys = store.keys(
        fingerprint=fingerprint,
        tool_call_id=tool_call_id,
        request_id=request_id,
    )
    with store.locked(keys):
        cached = store.load(keys)
        if cached is not None:
            cached_metadata = dict(cached.get("metadata") or {})
            cached_metadata.update(
                {"tool_call_id": tool_call_id, "request_id": request_id}
            )
            cached["metadata"] = cached_metadata
            return cached

        registry = ImageGenerationProviderRegistry()
        registry.register(SenseNovaImageProvider(config=config, transport=transport))
        result = ImageGenerationService(registry).generate(
            request,
            provider_name="sensenova",
            output_dir=output_root,
        ).to_dict()
        metadata = dict(result.get("metadata") or {})
        metadata.update(
            {
                "tool_call_id": tool_call_id,
                "request_id": request_id,
                "request_fingerprint": fingerprint,
                "idempotency_hit": False,
            }
        )
        result["metadata"] = metadata
        store.save(keys, result)
        return result
