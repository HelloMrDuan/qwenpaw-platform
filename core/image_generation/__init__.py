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
from .idempotency import ImageGenerationIdempotencyStore
from .registry import ImageGenerationProviderRegistry
from .routing import route_image_request
from .service import ImageGenerationService
from .sizing import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_IMAGE_SIZE,
    SENSENOVA_SIZE_BUCKETS,
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_IMAGE_SIZES,
    ImageSizePlan,
    UnsupportedNativeSizeError,
    resolve_size_plan,
)

__all__ = [
    "GeneratedImage",
    "GenerationProgress",
    "GenerationStatus",
    "ImageGenerationProvider",
    "ImageGenerationIdempotencyStore",
    "ImageGenerationProviderRegistry",
    "ImageGenerationRequest",
    "ImageGenerationResponse",
    "ImageGenerationService",
    "ImageGenerationServiceResult",
    "ImageSizePlan",
    "UnsupportedNativeSizeError",
    "DEFAULT_ASPECT_RATIO",
    "DEFAULT_IMAGE_SIZE",
    "SUPPORTED_ASPECT_RATIOS",
    "SUPPORTED_IMAGE_SIZES",
    "SENSENOVA_SIZE_BUCKETS",
    "ProgressCallback",
    "route_image_request",
    "resolve_size_plan",
]
