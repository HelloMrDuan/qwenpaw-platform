"""Immutable models for the local Extension lifecycle state machine."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from core.extensions.models import ExtensionType


LIFECYCLE_SCHEMA_VERSION = "qwenpaw-extension-lifecycle.v1"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ExtensionState(str, Enum):
    INSTALLED = "INSTALLED"
    ENABLED = "ENABLED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    DISABLED = "DISABLED"


class LifecycleAction(str, Enum):
    INSTALL = "install"
    VERIFY = "verify"
    ENABLE = "enable"
    DISABLE = "disable"
    START = "start"
    STOP = "stop"
    HEALTH = "health"
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"
    EXTERNAL_CHANGE = "external_change"


@dataclass(frozen=True, slots=True)
class LifecycleRecord:
    name: str
    type: ExtensionType
    version: str
    package_sha256: str
    state: ExtensionState
    revision: int
    last_action: LifecycleAction
    error: str | None = None
    schema_version: str = LIFECYCLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != LIFECYCLE_SCHEMA_VERSION:
            raise ValueError("unsupported lifecycle schema version")
        if not isinstance(self.name, str) or NAME_PATTERN.fullmatch(self.name) is None:
            raise ValueError("invalid Extension lifecycle name")
        if isinstance(self.type, str):
            object.__setattr__(self, "type", ExtensionType(self.type))
        if not isinstance(self.type, ExtensionType):
            raise TypeError("lifecycle type must be an ExtensionType")
        if not isinstance(self.version, str) or VERSION_PATTERN.fullmatch(self.version) is None:
            raise ValueError("invalid Extension lifecycle version")
        if (
            not isinstance(self.package_sha256, str)
            or SHA256_PATTERN.fullmatch(self.package_sha256) is None
        ):
            raise ValueError("invalid Extension lifecycle package_sha256")
        if isinstance(self.state, str):
            object.__setattr__(self, "state", ExtensionState(self.state))
        if not isinstance(self.state, ExtensionState):
            raise TypeError("state must be an ExtensionState")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("lifecycle revision must be a positive integer")
        if isinstance(self.last_action, str):
            object.__setattr__(self, "last_action", LifecycleAction(self.last_action))
        if not isinstance(self.last_action, LifecycleAction):
            raise TypeError("last_action must be a LifecycleAction")
        if self.error is not None and (
            not isinstance(self.error, str) or not self.error.strip()
        ):
            raise ValueError("lifecycle error must be null or non-empty text")

    def transition(
        self,
        state: ExtensionState,
        action: LifecycleAction,
        *,
        version: str | None = None,
        package_sha256: str | None = None,
        error: str | None = None,
    ) -> "LifecycleRecord":
        return replace(
            self,
            state=state,
            last_action=action,
            version=version or self.version,
            package_sha256=package_sha256 or self.package_sha256,
            revision=self.revision + 1,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "type": self.type.value,
            "version": self.version,
            "package_sha256": self.package_sha256,
            "state": self.state.value,
            "revision": self.revision,
            "last_action": self.last_action.value,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "LifecycleRecord":
        expected = {
            "schema_version",
            "name",
            "type",
            "version",
            "package_sha256",
            "state",
            "revision",
            "last_action",
            "error",
        }
        if not isinstance(document, Mapping) or set(document) != expected:
            raise ValueError("lifecycle record fields are invalid")
        return cls(**dict(document))


@dataclass(frozen=True, slots=True)
class HealthReport:
    name: str
    version: str
    state: ExtensionState
    healthy: bool
    deployment_verified: bool
    runtime_probe_performed: bool
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "state": self.state.value,
            "healthy": self.healthy,
            "deployment_verified": self.deployment_verified,
            "runtime_probe_performed": self.runtime_probe_performed,
            "code": self.code,
            "message": self.message,
        }
