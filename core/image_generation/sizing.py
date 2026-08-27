"""SenseNova-native size buckets and user-facing size resolution.

The values mirror the official OpenSenseNova ``sn-image-base`` SenseNova
backend.  The Agent deals in presets and ratios; only this adapter translates
those values to exact provider pixels.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
import re


DEFAULT_IMAGE_SIZE = "2k"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_LANDSCAPE_ASPECT_RATIO = "16:9"
DEFAULT_PORTRAIT_ASPECT_RATIO = "9:16"
SUPPORTED_IMAGE_SIZES = ("1k", "2k")
SUPPORTED_ASPECT_RATIOS = (
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "1:1",
    "16:9",
    "9:16",
    "9:21",
)

SENSENOVA_SIZE_BUCKETS: dict[str, dict[str, tuple[int, int]]] = {
    "1k": {
        "2:3": (1088, 1632),
        "3:2": (1632, 1088),
        "3:4": (1152, 1536),
        "4:3": (1536, 1152),
        "4:5": (1184, 1472),
        "5:4": (1472, 1184),
        "1:1": (1344, 1344),
        "16:9": (1792, 992),
        "9:16": (992, 1792),
        "9:21": (864, 2048),
    },
    "2k": {
        "2:3": (1664, 2496),
        "3:2": (2496, 1664),
        "3:4": (1760, 2368),
        "4:3": (2368, 1760),
        "4:5": (1824, 2272),
        "5:4": (2272, 1824),
        "1:1": (2048, 2048),
        "16:9": (2752, 1536),
        "9:16": (1536, 2752),
        "9:21": (1344, 3136),
    },
}

_PIXEL_SIZE = re.compile(r"^\s*(\d{1,5})\s*[xX×]\s*(\d{1,5})\s*$")
_PROMPT_PIXEL_SIZE = re.compile(r"(?<!\d)(\d{2,5})\s*[xX×]\s*(\d{2,5})(?!\d)")
_PROMPT_RATIO = re.compile(r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)")


class UnsupportedNativeSizeError(ValueError):
    """The caller explicitly required a non-native provider size."""


@dataclass(frozen=True, slots=True)
class ImageSizePlan:
    image_size: str
    requested_size: str | None
    requested_aspect_ratio: str
    provider_size: str
    provider_aspect_ratio: str
    final_size: str
    postprocess_required: bool
    fit_mode: str

    @property
    def provider_dimensions(self) -> tuple[int, int]:
        return parse_pixel_size(self.provider_size)

    @property
    def final_dimensions(self) -> tuple[int, int]:
        return parse_pixel_size(self.final_size)


def normalize_image_size(value: str | None) -> str:
    normalized = (value or DEFAULT_IMAGE_SIZE).strip().lower()
    if normalized not in SUPPORTED_IMAGE_SIZES:
        raise ValueError(
            "image_size must be one of: " + ", ".join(SUPPORTED_IMAGE_SIZES)
        )
    return normalized


def normalize_aspect_ratio(value: str | None) -> str:
    normalized = (value or DEFAULT_ASPECT_RATIO).strip().replace(" ", "")
    if normalized not in SUPPORTED_ASPECT_RATIOS:
        raise ValueError(
            "aspect_ratio must be one of: " + ", ".join(SUPPORTED_ASPECT_RATIOS)
        )
    return normalized


def parse_pixel_size(value: str) -> tuple[int, int]:
    match = _PIXEL_SIZE.fullmatch(str(value))
    if match is None:
        raise ValueError("requested_size must use WIDTHxHEIGHT positive pixels")
    width, height = (int(match.group(1)), int(match.group(2)))
    if width <= 0 or height <= 0:
        raise ValueError("requested_size dimensions must be positive")
    return width, height


def format_pixel_size(dimensions: tuple[int, int]) -> str:
    return f"{dimensions[0]}x{dimensions[1]}"


def exact_aspect_ratio(width: int, height: int) -> str:
    divisor = gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def nearest_provider_aspect_ratio(width: int, height: int) -> str:
    ratio = width / height
    return min(
        SUPPORTED_ASPECT_RATIOS,
        key=lambda item: abs(_ratio_value(item) - ratio),
    )


def provider_size(image_size: str, aspect_ratio: str) -> str:
    normalized_size = normalize_image_size(image_size)
    normalized_ratio = normalize_aspect_ratio(aspect_ratio)
    return format_pixel_size(
        SENSENOVA_SIZE_BUCKETS[normalized_size][normalized_ratio]
    )


def infer_requested_size(prompt: str, value: str | None) -> str | None:
    if value:
        return format_pixel_size(parse_pixel_size(value))
    match = _PROMPT_PIXEL_SIZE.search(prompt)
    if match is None:
        return None
    return format_pixel_size((int(match.group(1)), int(match.group(2))))


def infer_aspect_ratio(
    prompt: str,
    value: str | None,
    *,
    default_aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    landscape_aspect_ratio: str = DEFAULT_LANDSCAPE_ASPECT_RATIO,
    portrait_aspect_ratio: str = DEFAULT_PORTRAIT_ASPECT_RATIO,
) -> str:
    if value:
        return normalize_aspect_ratio(value)
    ratio_match = _PROMPT_RATIO.search(prompt)
    if ratio_match:
        candidate = f"{int(ratio_match.group(1))}:{int(ratio_match.group(2))}"
        return normalize_aspect_ratio(candidate)
    lowered = prompt.lower()
    if "横屏" in prompt or "landscape" in lowered:
        return normalize_aspect_ratio(landscape_aspect_ratio)
    if "竖屏" in prompt or "portrait" in lowered:
        return normalize_aspect_ratio(portrait_aspect_ratio)
    return normalize_aspect_ratio(default_aspect_ratio)


def resolve_size_plan(
    *,
    image_size: str | None,
    aspect_ratio: str | None,
    requested_size: str | None,
    fit_mode: str = "cover",
    require_native_size: bool = False,
) -> ImageSizePlan:
    normalized_image_size = normalize_image_size(image_size)
    normalized_ratio = normalize_aspect_ratio(aspect_ratio)
    normalized_fit = fit_mode.strip().lower()
    if normalized_fit not in {"contain", "cover", "stretch"}:
        raise ValueError("fit_mode must be contain, cover or stretch")

    if requested_size is None:
        native = provider_size(normalized_image_size, normalized_ratio)
        return ImageSizePlan(
            image_size=normalized_image_size,
            requested_size=None,
            requested_aspect_ratio=normalized_ratio,
            provider_size=native,
            provider_aspect_ratio=normalized_ratio,
            final_size=native,
            postprocess_required=False,
            fit_mode=normalized_fit,
        )

    requested_dimensions = parse_pixel_size(requested_size)
    normalized_requested_size = format_pixel_size(requested_dimensions)
    for bucket_size, ratios in SENSENOVA_SIZE_BUCKETS.items():
        for bucket_ratio, dimensions in ratios.items():
            if dimensions == requested_dimensions:
                native = format_pixel_size(dimensions)
                return ImageSizePlan(
                    image_size=bucket_size,
                    requested_size=normalized_requested_size,
                    requested_aspect_ratio=exact_aspect_ratio(*requested_dimensions),
                    provider_size=native,
                    provider_aspect_ratio=bucket_ratio,
                    final_size=native,
                    postprocess_required=False,
                    fit_mode=normalized_fit,
                )

    if require_native_size:
        raise UnsupportedNativeSizeError(
            f"{normalized_requested_size} is not a native SenseNova size"
        )

    exact_ratio = exact_aspect_ratio(*requested_dimensions)
    selected_ratio = (
        exact_ratio
        if exact_ratio in SUPPORTED_ASPECT_RATIOS
        else nearest_provider_aspect_ratio(*requested_dimensions)
    )
    native = provider_size(normalized_image_size, selected_ratio)
    return ImageSizePlan(
        image_size=normalized_image_size,
        requested_size=normalized_requested_size,
        requested_aspect_ratio=exact_ratio,
        provider_size=native,
        provider_aspect_ratio=selected_ratio,
        final_size=normalized_requested_size,
        postprocess_required=True,
        fit_mode=normalized_fit,
    )


def _ratio_value(value: str) -> float:
    width, height = (int(item) for item in value.split(":", 1))
    return width / height
