"""Contracts for provider-neutral text-to-image execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from core.contracts.artifact import Artifact

from .sizing import (
    DEFAULT_IMAGE_SIZE,
    infer_aspect_ratio,
    infer_requested_size,
    resolve_size_plan,
)


class GenerationStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    aspect_ratio: str | None = None
    image_size: str = DEFAULT_IMAGE_SIZE
    requested_size: str | None = None
    fit_mode: str = "cover"
    require_native_size: bool = False
    seed: int | None = None
    model: str | None = None
    count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be non-empty text")
        if not isinstance(self.negative_prompt, str):
            raise TypeError("negative_prompt must be text")
        resolved_ratio = infer_aspect_ratio(self.prompt, self.aspect_ratio)
        resolved_requested_size = infer_requested_size(
            self.prompt,
            self.requested_size,
        )
        object.__setattr__(self, "aspect_ratio", resolved_ratio)
        object.__setattr__(self, "requested_size", resolved_requested_size)
        resolve_size_plan(
            image_size=self.image_size,
            aspect_ratio=resolved_ratio,
            requested_size=resolved_requested_size,
            fit_mode=self.fit_mode,
            require_native_size=self.require_native_size,
        )
        if not isinstance(self.count, int) or isinstance(self.count, bool):
            raise TypeError("count must be an integer")
        if not 1 <= self.count <= 8:
            raise ValueError("count must be between 1 and 8")
        if self.seed is not None and (
            not isinstance(self.seed, int) or isinstance(self.seed, bool) or self.seed < 0
        ):
            raise ValueError("seed must be a non-negative integer or null")
        if self.model is not None and (
            not isinstance(self.model, str) or not self.model.strip()
        ):
            raise ValueError("model must be non-empty text or null")

    @property
    def size_plan(self):
        return resolve_size_plan(
            image_size=self.image_size,
            aspect_ratio=self.aspect_ratio,
            requested_size=self.requested_size,
            fit_mode=self.fit_mode,
            require_native_size=self.require_native_size,
        )


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    path: Path
    filename: str
    mime_type: str
    width: int
    height: int
    seed: int | None = None
    source_url: str | None = None
    requested_size: str | None = None
    requested_aspect_ratio: str = ""
    image_size: str = ""
    provider_size: str = ""
    provider_aspect_ratio: str = ""
    final_size: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        if self.mime_type not in {"image/png", "image/jpeg"}:
            raise ValueError("generated images must be PNG or JPEG")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("generated image dimensions must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "filename": self.filename,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "requested_size": self.requested_size,
            "requested_aspect_ratio": self.requested_aspect_ratio,
            "image_size": self.image_size,
            "provider_size": self.provider_size,
            "provider_aspect_ratio": self.provider_aspect_ratio,
            "final_size": self.final_size,
        }


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    status: GenerationStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"status": self.status.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class ImageGenerationResponse:
    status: GenerationStatus
    images: tuple[GeneratedImage, ...] = ()
    provider: str = ""
    model: str = ""
    seed: int | None = None
    duration: float = 0.0
    error: str | None = None
    error_code: str | None = None
    task_id: str | None = None
    requested_size: str | None = None
    requested_aspect_ratio: str = ""
    image_size: str = ""
    provider_size: str = ""
    provider_aspect_ratio: str = ""
    final_size: str = ""
    retryable: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            object.__setattr__(self, "status", GenerationStatus(self.status))
        if self.status is GenerationStatus.SUCCESS and not self.images:
            raise ValueError("SUCCESS requires at least one generated image")
        if self.status is not GenerationStatus.SUCCESS and self.images:
            raise ValueError("non-success responses cannot contain images")
        if self.duration < 0:
            raise ValueError("duration cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        result = {
            "status": self.status.value,
            "images": [image.to_dict() for image in self.images],
            "provider": self.provider,
            "model": self.model,
            "seed": self.seed,
            "duration": self.duration,
            "task_id": self.task_id,
            "requested_size": self.requested_size,
            "requested_aspect_ratio": self.requested_aspect_ratio,
            "image_size": self.image_size,
            "provider_size": self.provider_size,
            "provider_aspect_ratio": self.provider_aspect_ratio,
            "final_size": self.final_size,
            "retryable": self.retryable,
        }
        if self.error is not None:
            result["error"] = self.error
        if self.error_code is not None:
            result["error_code"] = self.error_code
        return result


@dataclass(frozen=True, slots=True)
class ImageGenerationServiceResult:
    response: ImageGenerationResponse
    artifacts: tuple[Artifact, ...] = ()
    progress: tuple[GenerationProgress, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.response.status is GenerationStatus.SUCCESS and (
            len(self.artifacts) != len(self.response.images)
        ):
            raise ValueError("every generated image must have one Artifact")
        if self.response.status is not GenerationStatus.SUCCESS and self.artifacts:
            raise ValueError("failed generation cannot publish Artifacts")

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.response.to_dict(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "progress": [event.to_dict() for event in self.progress],
            "metadata": dict(self.metadata),
        }
