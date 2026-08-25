"""External-process health and lifecycle bridge for Plugin/Adapter extensions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.extensions import (
    ExtensionMetadata,
    ExtensionRegistry,
    ExtensionRuntime,
    ExtensionType,
)
from core.extensions.lifecycle import (
    ExtensionLifecycleError,
    ExtensionLifecycleManager,
    ExtensionState,
    HealthReport,
)


ALLOWED_EXTENSION_NAME = "telegram"


@dataclass(frozen=True, slots=True)
class _AllowedExternalExtension:
    source_root: str
    type: ExtensionType
    runtime: ExtensionRuntime
    entrypoint: str


ALLOWED_EXTERNAL_EXTENSIONS = {
    "telegram": _AllowedExternalExtension(
        source_root="adapters",
        type=ExtensionType.ADAPTER,
        runtime=ExtensionRuntime.PYTHON,
        entrypoint="recovered/telegram_bridge_main.py",
    ),
    "wecom": _AllowedExternalExtension(
        source_root="plugins",
        type=ExtensionType.PLUGIN,
        runtime=ExtensionRuntime.NODE,
        entrypoint="recovered/wecom-node/wecom_bridge.mjs",
    ),
    "wechat-customer": _AllowedExternalExtension(
        source_root="plugins",
        type=ExtensionType.PLUGIN,
        runtime=ExtensionRuntime.PYTHON,
        entrypoint="recovered/wecom_kf_gateway_v345.py",
    ),
    "wechat-mp": _AllowedExternalExtension(
        source_root="plugins",
        type=ExtensionType.PLUGIN,
        runtime=ExtensionRuntime.PYTHON,
        entrypoint="recovered/wechat_mp_gateway.py",
    ),
    "hermes": _AllowedExternalExtension(
        source_root="plugins",
        type=ExtensionType.PLUGIN,
        runtime=ExtensionRuntime.PYTHON,
        entrypoint="recovered/hermes-agent-main/gateway/run.py",
    ),
}


class ExternalServiceState(str, Enum):
    UNKNOWN = "UNKNOWN"
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExternalServiceSnapshot:
    """Credential-free result supplied by an external service/process probe."""

    state: ExternalServiceState
    reachable: bool
    detail: str

    def __post_init__(self) -> None:
        if isinstance(self.state, str):
            object.__setattr__(self, "state", ExternalServiceState(self.state))
        if not isinstance(self.state, ExternalServiceState):
            raise TypeError("state must be an ExternalServiceState")
        if not isinstance(self.reachable, bool):
            raise TypeError("reachable must be a boolean")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("detail must be non-empty text")


@dataclass(frozen=True, slots=True)
class PluginRuntimeDescriptor:
    """Validated source identity for an external Plugin/Adapter process."""

    name: str
    version: str
    type: ExtensionType
    runtime: ExtensionRuntime
    manifest_path: Path
    entrypoint_path: Path

    def __post_init__(self) -> None:
        if self.type not in {ExtensionType.PLUGIN, ExtensionType.ADAPTER}:
            raise ValueError("Plugin Runtime Bridge requires plugin or adapter metadata")
        if not self.manifest_path.is_file():
            raise ValueError(f"Extension Manifest not found: {self.manifest_path}")
        if not self.entrypoint_path.is_file():
            raise ValueError(f"historical entrypoint not found: {self.entrypoint_path}")


@runtime_checkable
class ExternalServiceProbe(Protocol):
    def check(self, descriptor: PluginRuntimeDescriptor) -> ExternalServiceSnapshot:
        """Observe an already externalized process without starting it."""
        ...


class PluginRuntimeBridgeError(RuntimeError):
    """Raised when Plugin/Adapter discovery or lifecycle synchronization fails."""


class _UnavailableProbe:
    def check(self, descriptor: PluginRuntimeDescriptor) -> ExternalServiceSnapshot:
        return ExternalServiceSnapshot(
            state=ExternalServiceState.UNKNOWN,
            reachable=False,
            detail=f"No external service probe configured for {descriptor.name}",
        )


class PluginRuntimeBridge:
    """Synchronize a probed external service with the local lifecycle model."""

    def __init__(
        self,
        repository_root: str | Path,
        registry: ExtensionRegistry,
        lifecycle_manager: ExtensionLifecycleManager,
        *,
        probe: ExternalServiceProbe | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.registry = registry
        self.lifecycle_manager = lifecycle_manager
        self.probe = probe or _UnavailableProbe()

    def describe(self, name: str = ALLOWED_EXTENSION_NAME) -> PluginRuntimeDescriptor:
        metadata = self._metadata(name)
        allowed = ALLOWED_EXTERNAL_EXTENSIONS[name]
        if metadata.entrypoint != allowed.entrypoint:
            raise PluginRuntimeBridgeError(
                f"{name} entrypoint differs from the recovered allowlist"
            )
        extension_root = (
            self.repository_root / allowed.source_root / name
        ).resolve()
        manifest_path = extension_root / "manifest.yaml"
        entrypoint_path = (
            extension_root / Path(*Path(allowed.entrypoint).parts)
        ).resolve()
        if not entrypoint_path.is_relative_to(extension_root):
            raise PluginRuntimeBridgeError(
                f"{name} historical entrypoint is not allowed"
            )
        return PluginRuntimeDescriptor(
            name=metadata.name,
            version=metadata.version,
            type=metadata.type,
            runtime=metadata.runtime,
            manifest_path=manifest_path,
            entrypoint_path=entrypoint_path,
        )

    def health(
        self,
        name: str = ALLOWED_EXTENSION_NAME,
        *,
        probe: ExternalServiceProbe | None = None,
    ) -> HealthReport:
        descriptor = self.describe(name)
        try:
            local = self.lifecycle_manager.health(name)
        except ExtensionLifecycleError as exc:
            raise PluginRuntimeBridgeError(str(exc)) from exc
        if not local.deployment_verified:
            return local
        if local.state is ExtensionState.DISABLED:
            return local

        service_probe = probe or self.probe
        if not isinstance(service_probe, ExternalServiceProbe):
            raise TypeError("probe must implement check(descriptor)")
        try:
            snapshot = service_probe.check(descriptor)
        except Exception as exc:
            snapshot = ExternalServiceSnapshot(
                state=ExternalServiceState.FAILED,
                reachable=False,
                detail=f"external service probe failed: {exc}",
            )
        if not isinstance(snapshot, ExternalServiceSnapshot):
            raise PluginRuntimeBridgeError(
                "external service probe must return ExternalServiceSnapshot"
            )
        return self._synchronize(descriptor, snapshot)

    def _synchronize(
        self,
        descriptor: PluginRuntimeDescriptor,
        snapshot: ExternalServiceSnapshot,
    ) -> HealthReport:
        try:
            record = self.lifecycle_manager.get(descriptor.name)
            if snapshot.state is ExternalServiceState.RUNNING and snapshot.reachable:
                if record.state is ExtensionState.FAILED:
                    record = self.lifecycle_manager.verify(descriptor.name)
                if record.state is ExtensionState.INSTALLED:
                    record = self.lifecycle_manager.enable(descriptor.name)
                if record.state is ExtensionState.ENABLED:
                    record = self.lifecycle_manager.start(descriptor.name)
                if record.state is not ExtensionState.RUNNING:
                    raise PluginRuntimeBridgeError(
                        f"cannot synchronize running service from {record.state.value}"
                    )
                return self._report(
                    record.state,
                    descriptor,
                    healthy=True,
                    code="SERVICE_RUNNING",
                    message=snapshot.detail,
                )

            if snapshot.state is ExternalServiceState.STOPPED:
                if record.state is ExtensionState.RUNNING:
                    record = self.lifecycle_manager.stop(descriptor.name)
                return self._report(
                    record.state,
                    descriptor,
                    healthy=False,
                    code="SERVICE_STOPPED",
                    message=snapshot.detail,
                )

            failed = self.lifecycle_manager.fail(descriptor.name, snapshot.detail)
            code = (
                "SERVICE_UNREACHABLE"
                if snapshot.state is ExternalServiceState.RUNNING
                else f"SERVICE_{snapshot.state.value}"
            )
            return self._report(
                failed.state,
                descriptor,
                healthy=False,
                code=code,
                message=snapshot.detail,
            )
        except ExtensionLifecycleError as exc:
            raise PluginRuntimeBridgeError(str(exc)) from exc

    @staticmethod
    def _report(
        state: ExtensionState,
        descriptor: PluginRuntimeDescriptor,
        *,
        healthy: bool,
        code: str,
        message: str,
    ) -> HealthReport:
        return HealthReport(
            name=descriptor.name,
            version=descriptor.version,
            state=state,
            healthy=healthy,
            deployment_verified=True,
            runtime_probe_performed=True,
            code=code,
            message=message,
        )

    def _metadata(self, name: str) -> ExtensionMetadata:
        allowed = ALLOWED_EXTERNAL_EXTENSIONS.get(name)
        if allowed is None:
            raise PluginRuntimeBridgeError(
                "external Plugin Runtime Bridge does not allow this Extension"
            )
        metadata = self.registry.get(name)
        if metadata is None:
            raise PluginRuntimeBridgeError(f"Extension is not registered: {name}")
        if metadata.type is not allowed.type:
            raise PluginRuntimeBridgeError(
                f"{name} must be registered as {allowed.type.value}"
            )
        if metadata.runtime is not allowed.runtime:
            raise PluginRuntimeBridgeError(
                f"{name} recovered runtime must be {allowed.runtime.value}"
            )
        return metadata
