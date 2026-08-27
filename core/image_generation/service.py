"""Provider-neutral generation orchestration and Artifact conversion."""

from __future__ import annotations

from dataclasses import replace
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
        if (
            response.status is GenerationStatus.SUCCESS
            and request.size_plan.postprocess_required
        ):
            try:
                response = self._postprocess_response(
                    response,
                    request=request,
                    output_dir=Path(output_dir),
                )
            except Exception as exc:
                response = replace(
                    response,
                    status=GenerationStatus.FAILED,
                    images=(),
                    error=f"final image sizing failed: {exc}",
                    error_code="POSTPROCESS_FAILED",
                    retryable=False,
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
                "requested_size": image.requested_size,
                "requested_aspect_ratio": image.requested_aspect_ratio,
                "image_size": image.image_size,
                "provider_size": image.provider_size,
                "provider_aspect_ratio": image.provider_aspect_ratio,
                "final_size": image.final_size,
            },
        )

    @staticmethod
    def _postprocess_response(
        response: ImageGenerationResponse,
        *,
        request: ImageGenerationRequest,
        output_dir: Path,
    ) -> ImageGenerationResponse:
        """Delegate exact final sizing to the existing image-toolkit."""

        from core.productivity_skills.handlers.image_tools import execute

        width, height = request.size_plan.final_dimensions
        finalized = []
        for image in response.images:
            result = execute(
                "image-toolkit",
                {
                    "operation": "fit",
                    "input": str(image.path),
                    "width": width,
                    "height": height,
                    "fit_mode": request.fit_mode,
                    "output_dir": str(output_dir),
                },
            )
            if result.get("status") != "SUCCESS" or not result.get("artifacts"):
                detail = result.get("error") or result.get("message") or result
                raise RuntimeError(str(detail))
            item = result["artifacts"][0]
            final_path = (output_dir / item["filename"]).resolve()
            if not final_path.is_file():
                raise FileNotFoundError(final_path)
            finalized.append(
                replace(
                    image,
                    path=final_path,
                    filename=final_path.name,
                    width=width,
                    height=height,
                    final_size=f"{width}x{height}",
                )
            )
        return replace(
            response,
            images=tuple(finalized),
            final_size=f"{width}x{height}",
            error=None,
            error_code=None,
            retryable=False,
        )
