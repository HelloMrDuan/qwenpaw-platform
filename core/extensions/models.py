"""Static metadata models for discoverable workspace extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    executor: Mapping[str, str] | None = None
    schemas: Mapping[str, str] = field(default_factory=dict)
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    events: Sequence[str] = field(default_factory=tuple)
    tests: Sequence[str] = field(default_factory=tuple)

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

        if self.executor is not None:
            if not isinstance(self.executor, Mapping):
                raise TypeError("executor must be a mapping or None")
            executor = dict(self.executor)
            if set(executor) != {"runtime", "path", "callable"}:
                raise ValueError("executor must contain runtime, path, and callable")
            for field_name, value in executor.items():
                _require_text(value, f"executor.{field_name}")
            if executor["runtime"] != self.runtime.value:
                raise ValueError("executor.runtime must agree with runtime")
            if executor["path"] != self.entrypoint:
                raise ValueError("executor.path must agree with entrypoint")
            object.__setattr__(self, "executor", executor)

        for field_name in ("schemas", "artifacts"):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise TypeError(f"{field_name} must be a mapping")
            object.__setattr__(self, field_name, dict(value))

        for field_name in ("events", "tests"):
            value = getattr(self, field_name)
            if isinstance(value, (str, bytes)):
                raise TypeError(f"{field_name} must be a sequence of strings")
            normalized = tuple(value)
            if not all(isinstance(item, str) and item.strip() for item in normalized):
                raise ValueError(f"{field_name} must contain only non-empty strings")
            object.__setattr__(self, field_name, normalized)

        skill_fields_present = any(
            (
                self.executor is not None,
                bool(self.schemas),
                bool(self.artifacts),
                bool(self.events),
                bool(self.tests),
            )
        )
        if self.type is ExtensionType.SKILL:
            if not all(
                (
                    self.executor is not None,
                    bool(self.schemas),
                    bool(self.artifacts),
                    bool(self.events),
                    bool(self.tests),
                )
            ):
                raise ValueError("skill metadata requires all Skill Manifest fields")
        elif skill_fields_present:
            raise ValueError("plugin and adapter metadata cannot contain Skill fields")

    def to_dict(self) -> dict[str, Any]:
        document = {
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
        if self.type is ExtensionType.SKILL:
            document.update(
                {
                    "executor": dict(self.executor or {}),
                    "schemas": dict(self.schemas),
                    "artifacts": dict(self.artifacts),
                    "events": list(self.events),
                    "tests": list(self.tests),
                }
            )
        return document
