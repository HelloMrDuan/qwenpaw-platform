"""Provider contract for replaceable image-generation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from .contracts import GenerationStatus, ImageGenerationRequest, ImageGenerationResponse


ProgressCallback = Callable[[GenerationStatus, str], None]


class ImageGenerationProvider(ABC):
    """One provider implementation; Tool code must depend on this contract only."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def generate(
        self,
        request: ImageGenerationRequest,
        *,
        output_dir: Path,
        progress: ProgressCallback | None = None,
    ) -> ImageGenerationResponse:
        ...
