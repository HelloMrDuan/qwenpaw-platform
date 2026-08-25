"""Static metadata models for discoverable workspace extensions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class ExtensionType(str, Enum):
    """Extension families scanned by the local registry."""

    PLUGIN = "plugin"
    ADAPTER = "adapter"
    SKILL = "skill"


class ExtensionRuntime(str, Enum):
    """Primary process runtime declared by an Extension Manifest."""

    PYTHON = "python"
    NODE = "node"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class ExtensionMetadata:
    """Validated, non-executable projection of one Extension Manifest."""

    name: str
    type: ExtensionType
    version: str
    runtime: ExtensionRuntime
    entrypoint: str
    healthcheck: Mapping[str, str] | None
    dependencies: Sequence[str]

    def __post_init__(self) -> None:
        for field_name in ("name", "version", "entrypoint"):
            _require_text(getattr(self, field_name), field_name)

        if isinstance(self.type, str):
            try:
                object.__setattr__(self, "type", ExtensionType(self.type))
            except ValueError as exc:
                raise ValueError(f"unsupported extension type: {self.type}") from exc
        elif not isinstance(self.type, ExtensionType):
            raise TypeError("type must be an ExtensionType or supported string")

        if isinstance(self.runtime, str):
            try:
                object.__setattr__(self, "runtime", ExtensionRuntime(self.runtime))
            except ValueError as exc:
                raise ValueError(f"unsupported extension runtime: {self.runtime}") from exc
        elif not isinstance(self.runtime, ExtensionRuntime):
            raise TypeError("runtime must be an ExtensionRuntime or supported string")

        if isinstance(self.dependencies, (str, bytes)):
            raise TypeError("dependencies must be a sequence of strings")
        dependencies = tuple(self.dependencies)
        if not all(isinstance(item, str) and item.strip() for item in dependencies):
            raise ValueError("dependencies must contain only non-empty strings")
        object.__setattr__(self, "dependencies", dependencies)

        if self.healthcheck is not None:
            if not isinstance(self.healthcheck, Mapping):
                raise TypeError("healthcheck must be a mapping or None")
            healthcheck = dict(self.healthcheck)
            if set(healthcheck) != {"type", "target"}:
                raise ValueError("healthcheck must contain only type and target")
            _require_text(healthcheck["type"], "healthcheck.type")
            _require_text(healthcheck["target"], "healthcheck.target")
            object.__setattr__(self, "healthcheck", healthcheck)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "version": self.version,
            "runtime": self.runtime.value,
            "entrypoint": self.entrypoint,
            "healthcheck": (
                dict(self.healthcheck) if self.healthcheck is not None else None
            ),
            "dependencies": list(self.dependencies),
        }
