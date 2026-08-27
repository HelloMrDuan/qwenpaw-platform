"""Factories for optional model Runtime adapters."""

from __future__ import annotations

from typing import Any, Mapping

from .errors import RuntimeAdapterError, RuntimeExecutionError, RuntimeUnavailableError
from .faster_whisper import FasterWhisperAdapter, FasterWhisperConfig
from .rembg import RembgAdapter, RembgConfig


_ADAPTER_FACTORIES = {
    "asr": FasterWhisperAdapter.from_request,
    "background_removal": RembgAdapter.from_request,
}


def registered_runtime_capabilities() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTER_FACTORIES))


def get_runtime(capability: str, request: Mapping[str, Any] | None = None) -> object:
    try:
        factory = _ADAPTER_FACTORIES[capability]
    except KeyError as exc:
        raise RuntimeUnavailableError(f"No Runtime adapter is registered for {capability}") from exc
    return factory(request)


def get_asr_runtime(request: Mapping[str, Any] | None = None) -> FasterWhisperAdapter:
    return get_runtime("asr", request)  # type: ignore[return-value]


def get_segmentation_runtime(request: Mapping[str, Any] | None = None) -> RembgAdapter:
    return get_runtime("background_removal", request)  # type: ignore[return-value]


__all__ = [
    "FasterWhisperAdapter",
    "FasterWhisperConfig",
    "RembgAdapter",
    "RembgConfig",
    "RuntimeAdapterError",
    "RuntimeExecutionError",
    "RuntimeUnavailableError",
    "get_asr_runtime",
    "get_runtime",
    "get_segmentation_runtime",
    "registered_runtime_capabilities",
]
