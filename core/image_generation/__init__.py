"""Provider-neutral image-generation Runtime capability."""

from .contracts import (
    GeneratedImage,
    GenerationProgress,
    GenerationStatus,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageGenerationServiceResult,
)
from .provider import ImageGenerationProvider, ProgressCallback
from .registry import ImageGenerationProviderRegistry
from .routing import route_image_request
from .service import ImageGenerationService

__all__ = [
    "GeneratedImage",
    "GenerationProgress",
    "GenerationStatus",
    "ImageGenerationProvider",
    "ImageGenerationProviderRegistry",
    "ImageGenerationRequest",
    "ImageGenerationResponse",
    "ImageGenerationService",
    "ImageGenerationServiceResult",
    "ProgressCallback",
    "route_image_request",
]
