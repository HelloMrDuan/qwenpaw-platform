"""Immutable records for offline AgentScope Workspace deployment planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
import re
from typing import Any, Sequence

from core.extensions import ExtensionType


AGENTSCOPE_INSTALL_PLAN_VERSION = "qwenpaw-agentscope-install-plan.v1"
AGENTSCOPE_ROLLBACK_PLAN_VERSION = "qwenpaw-agentscope-rollback-plan.v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def _normalized_strings(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be a sequence of strings")
    normalized = tuple(values)
    if not all(isinstance(value, str) and value.strip() for value in normalized):
        raise ValueError(f"{field_name} must contain only non-empty strings")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class ExtensionPackageDescriptor:
    archive: Path
    name: str
    type: ExtensionType
    version: str
    sha256: str
    files: Sequence[str]
    required_secrets: Sequence[str]

    def __post_init__(self) -> None:
        archive = Path(self.archive).resolve()
        if not archive.is_file():
            raise ValueError(f"Extension package does not exist: {archive}")
        object.__setattr__(self, "archive", archive)
        for field_name in ("name", "version"):
            object.__setattr__(
                self,
                field_name,
                _require_text(getattr(self, field_name), field_name),
            )
        if isinstance(self.type, str):
            object.__setattr__(self, "type", ExtensionType(self.type))
        if not isinstance(self.type, ExtensionType):
            raise TypeError("type must be an ExtensionType")
        if not isinstance(self.sha256, str) or SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
        files = _normalized_strings(self.files, "files")
        if tuple(sorted(files)) != files:
            raise ValueError("files must use stable sorted order")
        if "manifest.yaml" not in files:
            raise ValueError("package files must contain manifest.yaml")
        object.__setattr__(self, "files", files)
        secrets = _normalized_strings(self.required_secrets, "required_secrets")
        object.__setattr__(self, "required_secrets", tuple(sorted(secrets)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive": str(self.archive),
            "name": self.name,
            "type": self.type.value,
            "version": self.version,
            "sha256": self.sha256,
            "files": list(self.files),
            "required_secrets": list(self.required_secrets),
        }


@dataclass(frozen=True, slots=True)
class WorkspaceMapping:
    extension_name: str
    extension_type: ExtensionType
    workspace_root: Path
    relative_target: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "extension_name",
            _require_text(self.extension_name, "extension_name"),
        )
        if isinstance(self.extension_type, str):
            object.__setattr__(
                self, "extension_type", ExtensionType(self.extension_type)
            )
        if not isinstance(self.extension_type, ExtensionType):
            raise TypeError("extension_type must be an ExtensionType")
        root = Path(self.workspace_root).resolve()
        object.__setattr__(self, "workspace_root", root)
        relative = PurePosixPath(
            _require_text(self.relative_target, "relative_target")
        )
        if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
            raise ValueError("relative_target must remain inside the Workspace")
        if relative.as_posix() != self.relative_target:
            raise ValueError("relative_target must use normalized POSIX separators")
        object.__setattr__(self, "relative_target", relative.as_posix())
        if not self.target_directory.is_relative_to(root):
            raise ValueError("target directory escapes the Workspace root")

    @property
    def target_directory(self) -> Path:
        relative = PurePosixPath(self.relative_target)
        return self.workspace_root.joinpath(*relative.parts).resolve()

    def to_dict(self) -> dict[str, Any]:
        return {
            "extension_name": self.extension_name,
            "extension_type": self.extension_type.value,
            "workspace_root": str(self.workspace_root),
            "relative_target": self.relative_target,
            "target_directory": str(self.target_directory),
        }


@dataclass(frozen=True, slots=True)
class SecretRequirementCheck:
    required: Sequence[str]
    available: Sequence[str]
    missing: Sequence[str]

    def __post_init__(self) -> None:
        required = tuple(sorted(_normalized_strings(self.required, "required")))
        available = tuple(sorted(_normalized_strings(self.available, "available")))
        missing = tuple(sorted(_normalized_strings(self.missing, "missing")))
        if not set(available).issubset(required):
            raise ValueError("available secrets must be declared requirements")
        if set(missing) != set(required) - set(available):
            raise ValueError("missing secrets must equal required minus available")
        object.__setattr__(self, "required", required)
        object.__setattr__(self, "available", available)
        object.__setattr__(self, "missing", missing)

    @property
    def satisfied(self) -> bool:
        return not self.missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": list(self.required),
            "available": list(self.available),
            "missing": list(self.missing),
            "satisfied": self.satisfied,
        }


class InstallAction(str, Enum):
    VERIFY_PACKAGE = "verify_package"
    CHECK_SECRETS = "check_secrets"
    PREPARE_TARGET = "prepare_target"
    INSTALL_PAYLOAD = "install_payload"
    VERIFY_WORKSPACE = "verify_workspace"


@dataclass(frozen=True, slots=True)
class InstallPlanStep:
    order: int
    action: InstallAction
    target: str
    blocking: bool = True

    def __post_init__(self) -> None:
        if type(self.order) is not int or self.order < 1:
            raise ValueError("install step order must be a positive integer")
        if isinstance(self.action, str):
            object.__setattr__(self, "action", InstallAction(self.action))
        if not isinstance(self.action, InstallAction):
            raise TypeError("action must be an InstallAction")
        object.__setattr__(self, "target", _require_text(self.target, "target"))
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action.value,
            "target": self.target,
            "blocking": self.blocking,
        }


@dataclass(frozen=True, slots=True)
class InstallPlan:
    plan_id: str
    package: ExtensionPackageDescriptor
    mapping: WorkspaceMapping
    secrets: SecretRequirementCheck
    steps: Sequence[InstallPlanStep]
    schema_version: str = AGENTSCOPE_INSTALL_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != AGENTSCOPE_INSTALL_PLAN_VERSION:
            raise ValueError("unsupported AgentScope Install Plan version")
        object.__setattr__(self, "plan_id", _require_text(self.plan_id, "plan_id"))
        if not isinstance(self.package, ExtensionPackageDescriptor):
            raise TypeError("package must be an ExtensionPackageDescriptor")
        if not isinstance(self.mapping, WorkspaceMapping):
            raise TypeError("mapping must be a WorkspaceMapping")
        if not isinstance(self.secrets, SecretRequirementCheck):
            raise TypeError("secrets must be a SecretRequirementCheck")
        if (
            self.package.name != self.mapping.extension_name
            or self.package.type is not self.mapping.extension_type
        ):
            raise ValueError("package and Workspace mapping identities must match")
        if isinstance(self.steps, (str, bytes)):
            raise TypeError("steps must be a sequence of InstallPlanStep objects")
        steps = tuple(self.steps)
        if not steps or not all(isinstance(item, InstallPlanStep) for item in steps):
            raise ValueError("steps must contain InstallPlanStep objects")
        if tuple(item.order for item in steps) != tuple(range(1, len(steps) + 1)):
            raise ValueError("install steps must use contiguous order starting at one")
        object.__setattr__(self, "steps", steps)

    @property
    def ready(self) -> bool:
        return self.secrets.satisfied

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "ready": self.ready,
            "package": self.package.to_dict(),
            "mapping": self.mapping.to_dict(),
            "secrets": self.secrets.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
        }


class RollbackAction(str, Enum):
    VERIFY_ROLLBACK_PACKAGE = "verify_rollback_package"
    CHECK_SECRETS = "check_secrets"
    PRESERVE_CURRENT_TARGET = "preserve_current_target"
    RESTORE_PAYLOAD = "restore_payload"
    VERIFY_WORKSPACE = "verify_workspace"


@dataclass(frozen=True, slots=True)
class RollbackPlanStep:
    order: int
    action: RollbackAction
    target: str
    blocking: bool = True

    def __post_init__(self) -> None:
        if type(self.order) is not int or self.order < 1:
            raise ValueError("rollback step order must be a positive integer")
        if isinstance(self.action, str):
            object.__setattr__(self, "action", RollbackAction(self.action))
        if not isinstance(self.action, RollbackAction):
            raise TypeError("action must be a RollbackAction")
        object.__setattr__(self, "target", _require_text(self.target, "target"))
        if not isinstance(self.blocking, bool):
            raise TypeError("blocking must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action.value,
            "target": self.target,
            "blocking": self.blocking,
        }


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    plan_id: str
    current_package: ExtensionPackageDescriptor
    rollback_package: ExtensionPackageDescriptor
    mapping: WorkspaceMapping
    secrets: SecretRequirementCheck
    steps: Sequence[RollbackPlanStep]
    schema_version: str = AGENTSCOPE_ROLLBACK_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != AGENTSCOPE_ROLLBACK_PLAN_VERSION:
            raise ValueError("unsupported AgentScope Rollback Plan version")
        object.__setattr__(self, "plan_id", _require_text(self.plan_id, "plan_id"))
        for field_name in ("current_package", "rollback_package"):
            if not isinstance(getattr(self, field_name), ExtensionPackageDescriptor):
                raise TypeError(
                    f"{field_name} must be an ExtensionPackageDescriptor"
                )
        if (
            self.current_package.name != self.rollback_package.name
            or self.current_package.type is not self.rollback_package.type
        ):
            raise ValueError("rollback packages must describe one Extension identity")
        if self.current_package.version == self.rollback_package.version:
            raise ValueError("rollback package must use a different version")
        if not isinstance(self.mapping, WorkspaceMapping):
            raise TypeError("mapping must be a WorkspaceMapping")
        if (
            self.mapping.extension_name != self.rollback_package.name
            or self.mapping.extension_type is not self.rollback_package.type
        ):
            raise ValueError("rollback package and Workspace mapping must match")
        if not isinstance(self.secrets, SecretRequirementCheck):
            raise TypeError("secrets must be a SecretRequirementCheck")
        if tuple(self.secrets.required) != tuple(self.rollback_package.required_secrets):
            raise ValueError("secret check must describe the rollback package")
        if isinstance(self.steps, (str, bytes)):
            raise TypeError("steps must be a sequence of RollbackPlanStep objects")
        steps = tuple(self.steps)
        if not steps or not all(isinstance(item, RollbackPlanStep) for item in steps):
            raise ValueError("steps must contain RollbackPlanStep objects")
        if tuple(item.order for item in steps) != tuple(range(1, len(steps) + 1)):
            raise ValueError("rollback steps must use contiguous order starting at one")
        object.__setattr__(self, "steps", steps)

    @property
    def ready(self) -> bool:
        return self.secrets.satisfied

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "ready": self.ready,
            "current_package": self.current_package.to_dict(),
            "rollback_package": self.rollback_package.to_dict(),
            "mapping": self.mapping.to_dict(),
            "secrets": self.secrets.to_dict(),
            "steps": [step.to_dict() for step in self.steps],
        }
