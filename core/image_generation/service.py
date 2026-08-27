"""Provider-neutral generation orchestration and Artifact conversion."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core.contracts.artifact import Artifact, ArtifactKind

from .contracts import (
    GenerationProgress,
    GenerationStatus,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationServiceResult,
)
from .registry import ImageGenerationProviderRegistry


class ImageGenerationService:
    def __init__(self, registry: ImageGenerationProviderRegistry) -> None:
        self.registry = registry

    def generate(
        self,
        request: ImageGenerationRequest,
        *,
        provider_name: str = "sensenova",
        output_dir: str | Path,
    ) -> ImageGenerationServiceResult:
        provider = self.registry.get(provider_name)
        if provider is None:
            response = ImageGenerationResponse(
                status=GenerationStatus.PROVIDER_NOT_CONFIGURED,
                provider=provider_name,
                model=request.model or "",
                seed=request.seed,
                error=f"image-generation provider is not registered: {provider_name}",
                error_code="PROVIDER_NOT_REGISTERED",
            )
            return ImageGenerationServiceResult(response=response)

        progress_events: list[GenerationProgress] = []

        def record(status: GenerationStatus, message: str) -> None:
            progress_events.append(GenerationProgress(status=status, message=message))

        response = provider.generate(
            request,
            output_dir=Path(output_dir),
            progress=record,
        )
        artifacts = (
            tuple(
                self._artifact(image, response=response)
                for image in response.images
            )
            if response.status is GenerationStatus.SUCCESS
            else ()
        )
        return ImageGenerationServiceResult(
            response=response,
            artifacts=artifacts,
            progress=tuple(progress_events),
            metadata={"capability": "image_generation"},
        )

    @staticmethod
    def _artifact(image, *, response: ImageGenerationResponse) -> Artifact:
        data = image.path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        return Artifact(
            id=f"sha256:{digest}",
            kind=ArtifactKind.IMAGE,
            name=image.filename,
            mime_type=image.mime_type,
            size_bytes=len(data),
            uri=f"artifact://{image.filename}",
            sha256=digest,
            dimensions={"width": image.width, "height": image.height},
            metadata={
                "provider": response.provider,
                "model": response.model,
                "seed": image.seed,
                "path": str(image.path),
            },
        )
