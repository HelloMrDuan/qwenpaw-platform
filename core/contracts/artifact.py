"""Artifact descriptors shared by messages, skills, and channel adapters.

This module defines data contracts only. It does not read, write, upload, or
otherwise manage artifact content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping


class ArtifactKind(str, Enum):
    """Supported artifact categories."""

    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Artifact:
    """A validated reference to content held by a future artifact store."""

    id: str
    kind: ArtifactKind
    name: str
    mime_type: str
    size_bytes: int
    uri: str
    sha256: str | None = None
    duration_ms: int | None = None
    dimensions: Mapping[str, int] | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.id, "id")
        _require_text(self.name, "name")
        _require_text(self.mime_type, "mime_type")
        _require_text(self.uri, "uri")

        if isinstance(self.kind, str):
            try:
                object.__setattr__(self, "kind", ArtifactKind(self.kind))
            except ValueError as exc:
                raise ValueError(f"unsupported artifact kind: {self.kind}") from exc
        elif not isinstance(self.kind, ArtifactKind):
            raise TypeError("kind must be an ArtifactKind or supported string")

        if not self.uri.startswith("artifact://"):
            raise ValueError("uri must use the artifact:// scheme")
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool):
            raise TypeError("size_bytes must be an integer")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be greater than or equal to zero")
        if self.sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        if self.duration_ms is not None:
            if not isinstance(self.duration_ms, int) or isinstance(self.duration_ms, bool):
                raise TypeError("duration_ms must be an integer")
            if self.duration_ms < 0:
                raise ValueError("duration_ms must be greater than or equal to zero")
        if self.dimensions is not None:
            if not isinstance(self.dimensions, Mapping):
                raise TypeError("dimensions must be a mapping")
            for key in ("width", "height"):
                value = self.dimensions.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    raise ValueError(f"dimensions.{key} must be a positive integer")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        """Return the wire-safe representation of this descriptor."""

        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "uri": self.uri,
            "sha256": self.sha256,
            "duration_ms": self.duration_ms,
            "dimensions": dict(self.dimensions) if self.dimensions is not None else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Artifact":
        """Build and validate an artifact from a decoded wire object."""

        if not isinstance(data, Mapping):
            raise TypeError("artifact data must be a mapping")
        return cls(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            mime_type=data["mime_type"],
            size_bytes=data["size_bytes"],
            uri=data["uri"],
            sha256=data.get("sha256"),
            duration_ms=data.get("duration_ms"),
            dimensions=data.get("dimensions"),
            metadata=data.get("metadata", {}),
        )
