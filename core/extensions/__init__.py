"""Local, non-executable discovery APIs for QwenPaw workspace extensions."""

from .loader import (
    ExtensionLoader,
    ManifestError,
    ManifestParseError,
    ManifestValidationError,
    MissingManifestError,
)
from .models import ExtensionMetadata, ExtensionRuntime, ExtensionType
from .registry import DuplicateExtensionError, ExtensionRegistry

__all__ = [
    "DuplicateExtensionError",
    "ExtensionLoader",
    "ExtensionMetadata",
    "ExtensionRegistry",
    "ExtensionRuntime",
    "ExtensionType",
    "ManifestError",
    "ManifestParseError",
    "ManifestValidationError",
    "MissingManifestError",
]
