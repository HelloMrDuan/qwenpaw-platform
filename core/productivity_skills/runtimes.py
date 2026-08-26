"""Deployment-injected interfaces for heavyweight optional model Runtimes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@runtime_checkable
class OCRRuntime(Protocol):
    def recognize(
        self,
        image: Path,
        *,
        languages: Sequence[str],
        layout: bool = False,
        tables: bool = False,
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ASRRuntime(Protocol):
    def transcribe(
        self,
        media: Path,
        *,
        language: str | None = None,
        diarization: bool = False,
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ImageRestorationRuntime(Protocol):
    def restore(
        self,
        image: Path,
        output: Path,
        *,
        stages: Sequence[str],
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class SegmentationRuntime(Protocol):
    def segment(
        self,
        image: Path,
        output: Path,
        *,
        alpha_matting: bool = False,
    ) -> Mapping[str, Any]: ...


class RuntimeRegistry:
    """Explicit registry; Skills never discover or download model weights."""

    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def register(self, capability: str, runtime: object) -> None:
        if not capability or runtime is None:
            raise ValueError("capability and runtime are required")
        self._values[capability] = runtime

    def get(self, capability: str) -> object | None:
        return self._values.get(capability)
