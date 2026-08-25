"""Local-only Extension lifecycle state manager."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from core.extensions.models import ExtensionType
from scripts.deploy_extension import (
    ACTIVE_SCHEMA_VERSION,
    DEFAULT_DEPLOYMENT_ROOT,
    ExtensionDeploymentError,
    deploy_extension,
)
from scripts.rollback_extension import (
    ExtensionRollbackError,
    rollback_extension as activate_rollback,
)
from scripts.verify_extension import (
    ExtensionVerificationError,
    verify_deployment,
    verify_package,
)

from .health import LocalHealthChecker
from .models import (
    ExtensionState,
    HealthReport,
    LifecycleAction,
    LifecycleRecord,
    NAME_PATTERN,
)


LIFECYCLE_FILE_NAME = "lifecycle.json"


class ExtensionLifecycleError(ValueError):
    """Base error for local lifecycle operations."""


class InvalidLifecycleTransition(ExtensionLifecycleError):
    """Raised when an operation is invalid for the current state."""


class LifecycleVerificationError(ExtensionLifecycleError):
    """Raised after a failed deployment verification marks the state FAILED."""


class ExtensionLifecycleManager:
    """Manage local state files without controlling any Runtime process."""

    def __init__(
        self,
        deployment_root: str | Path = DEFAULT_DEPLOYMENT_ROOT,
        *,
        health_checker: LocalHealthChecker | None = None,
    ) -> None:
        self.deployment_root = Path(deployment_root).resolve()
        self.health_checker = health_checker or LocalHealthChecker()

    def list(self) -> tuple[LifecycleRecord, ...]:
        if not self.deployment_root.is_dir():
            return ()
        records = []
        for extension_root in sorted(
            self.deployment_root.iterdir(), key=lambda path: path.name
        ):
            if extension_root.is_dir() and (extension_root / "current.json").is_file():
                records.append(self.get(extension_root.name))
        return tuple(records)

    def get(self, name: str) -> LifecycleRecord:
        extension_root = self._extension_root(name)
        current = self._read_json(extension_root / "current.json")
        try:
            current_record = self._record_from_current(current)
        except (TypeError, ValueError) as exc:
            raise ExtensionLifecycleError(
                f"invalid active Extension pointer: {extension_root / 'current.json'}"
            ) from exc
        lifecycle_path = extension_root / LIFECYCLE_FILE_NAME
        if not lifecycle_path.is_file():
            return current_record

        try:
            stored = LifecycleRecord.from_dict(self._read_json(lifecycle_path))
        except (TypeError, ValueError) as exc:
            raise ExtensionLifecycleError(
                f"invalid lifecycle record: {lifecycle_path}"
            ) from exc
        current_identity = (
            current_record.name,
            current_record.type,
            current_record.version,
            current_record.package_sha256,
        )
        stored_identity = (
            stored.name,
            stored.type,
            stored.version,
            stored.package_sha256,
        )
        if stored_identity != current_identity:
            return LifecycleRecord(
                name=current_record.name,
                type=current_record.type,
                version=current_record.version,
                package_sha256=current_record.package_sha256,
                state=ExtensionState.FAILED,
                revision=stored.revision + 1,
                last_action=LifecycleAction.EXTERNAL_CHANGE,
                error="active deployment changed outside Lifecycle Manager",
            )
        return stored

    def install(
        self,
        package_path: str | Path,
        *,
        expected_sha256: str | None = None,
    ) -> LifecycleRecord:
        package = self._verify_package(package_path, expected_sha256)
        extension_root = self.deployment_root / package.name
        current_path = extension_root / "current.json"
        if current_path.is_file():
            current = self._read_json(current_path)
            if (
                current.get("version") != package.version
                or current.get("package_sha256") != package.sha256
            ):
                raise ExtensionLifecycleError(
                    f"{package.name} is already installed; use upgrade for a new version"
                )
            record = self.get(package.name)
            self._deploy_package(package)
            if not (extension_root / LIFECYCLE_FILE_NAME).is_file():
                self._write_record(record)
            return record

        deployed = self._deploy_package(package)
        record = LifecycleRecord(
            name=deployed.name,
            type=deployed.type,
            version=deployed.version,
            package_sha256=deployed.package_sha256,
            state=ExtensionState.INSTALLED,
            revision=1,
            last_action=LifecycleAction.INSTALL,
        )
        self._write_record(record)
        return record

    def verify(self, name: str) -> LifecycleRecord:
        record = self.get(name)
        try:
            verified = verify_deployment(self._version_directory(record))
            if (
                verified.name != record.name
                or verified.type != record.type.value
                or verified.version != record.version
                or verified.package_sha256 != record.package_sha256
            ):
                raise ExtensionVerificationError(
                    "active deployment metadata differs from lifecycle record"
                )
        except ExtensionVerificationError as exc:
            failed = record.transition(
                ExtensionState.FAILED,
                LifecycleAction.VERIFY,
                error=str(exc),
            )
            self._write_record(failed)
            raise LifecycleVerificationError(str(exc)) from exc

        state = (
            ExtensionState.INSTALLED
            if record.state is ExtensionState.FAILED
            else record.state
        )
        verified_record = record.transition(
            state,
            LifecycleAction.VERIFY,
            error=None,
        )
        self._write_record(verified_record)
        return verified_record

    def enable(self, name: str) -> LifecycleRecord:
        record = self.get(name)
        if record.state in {ExtensionState.ENABLED, ExtensionState.RUNNING}:
            return record
        if record.state not in {ExtensionState.INSTALLED, ExtensionState.DISABLED}:
            self._invalid(record, LifecycleAction.ENABLE)
        return self._transition(record, ExtensionState.ENABLED, LifecycleAction.ENABLE)

    def disable(self, name: str) -> LifecycleRecord:
        record = self.get(name)
        if record.state is ExtensionState.DISABLED:
            return record
        return self._transition(record, ExtensionState.DISABLED, LifecycleAction.DISABLE)

    def start(self, name: str) -> LifecycleRecord:
        record = self.get(name)
        if record.state is ExtensionState.RUNNING:
            return record
        if record.state is not ExtensionState.ENABLED:
            self._invalid(record, LifecycleAction.START)
        return self._transition(record, ExtensionState.RUNNING, LifecycleAction.START)

    def stop(self, name: str) -> LifecycleRecord:
        record = self.get(name)
        if record.state is ExtensionState.ENABLED:
            return record
        if record.state is not ExtensionState.RUNNING:
            self._invalid(record, LifecycleAction.STOP)
        return self._transition(record, ExtensionState.ENABLED, LifecycleAction.STOP)

    def health(self, name: str) -> HealthReport:
        record = self.get(name)
        report = self.health_checker.check(record, self._version_directory(record))
        if report.state is ExtensionState.FAILED and record.state is not ExtensionState.FAILED:
            failed = record.transition(
                ExtensionState.FAILED,
                LifecycleAction.HEALTH,
                error=report.message,
            )
            self._write_record(failed)
        return report

    def upgrade(
        self,
        package_path: str | Path,
        *,
        expected_sha256: str | None = None,
    ) -> LifecycleRecord:
        package = self._verify_package(package_path, expected_sha256)
        record = self.get(package.name)
        if record.version == package.version:
            raise ExtensionLifecycleError("upgrade requires a different version")
        if record.type.value != package.type:
            raise ExtensionLifecycleError("upgrade cannot change the Extension type")
        deployed = self._deploy_package(package)
        next_state = self._post_version_change_state(record.state)
        upgraded = record.transition(
            next_state,
            LifecycleAction.UPGRADE,
            version=deployed.version,
            package_sha256=deployed.package_sha256,
            error=None,
        )
        self._write_record(upgraded)
        return upgraded

    def rollback(self, name: str, *, version: str | None = None) -> LifecycleRecord:
        record = self.get(name)
        try:
            result = activate_rollback(
                name,
                version=version,
                target_root=self.deployment_root,
            )
            verified = verify_deployment(result.version_directory)
        except (ExtensionRollbackError, ExtensionVerificationError) as exc:
            raise ExtensionLifecycleError(str(exc)) from exc
        rolled_back = record.transition(
            self._post_version_change_state(record.state),
            LifecycleAction.ROLLBACK,
            version=verified.version,
            package_sha256=verified.package_sha256,
            error=None,
        )
        self._write_record(rolled_back)
        return rolled_back

    @staticmethod
    def _post_version_change_state(state: ExtensionState) -> ExtensionState:
        if state in {ExtensionState.ENABLED, ExtensionState.RUNNING}:
            return ExtensionState.ENABLED
        if state is ExtensionState.DISABLED:
            return ExtensionState.DISABLED
        return ExtensionState.INSTALLED

    def _transition(
        self,
        record: LifecycleRecord,
        state: ExtensionState,
        action: LifecycleAction,
    ) -> LifecycleRecord:
        transitioned = record.transition(state, action, error=None)
        self._write_record(transitioned)
        return transitioned

    @staticmethod
    def _invalid(record: LifecycleRecord, action: LifecycleAction) -> None:
        raise InvalidLifecycleTransition(
            f"cannot {action.value} {record.name} from {record.state.value}"
        )

    def _extension_root(self, name: str) -> Path:
        if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
            raise ExtensionLifecycleError("Extension name is invalid")
        return self.deployment_root / name

    def _version_directory(self, record: LifecycleRecord) -> Path:
        return self.deployment_root / record.name / "versions" / record.version

    def _record_from_current(self, current: Mapping[str, Any]) -> LifecycleRecord:
        required = {
            "schema_version",
            "name",
            "type",
            "version",
            "package_sha256",
            "relative_path",
        }
        if set(current) != required:
            raise ExtensionLifecycleError("active Extension pointer fields are invalid")
        if current["schema_version"] != ACTIVE_SCHEMA_VERSION:
            raise ExtensionLifecycleError("active Extension pointer schema is unsupported")
        if current["relative_path"] != f"versions/{current['version']}":
            raise ExtensionLifecycleError("active Extension relative_path is inconsistent")
        return LifecycleRecord(
            name=str(current["name"]),
            type=ExtensionType(current["type"]),
            version=str(current["version"]),
            package_sha256=str(current["package_sha256"]),
            state=ExtensionState.INSTALLED,
            revision=1,
            last_action=LifecycleAction.INSTALL,
        )

    def _write_record(self, record: LifecycleRecord) -> None:
        path = self.deployment_root / record.name / LIFECYCLE_FILE_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(record.to_dict(), stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _read_json(path: Path) -> Mapping[str, Any]:
        if not path.is_file():
            raise ExtensionLifecycleError(f"Extension is not installed: {path.parent.name}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExtensionLifecycleError(f"invalid lifecycle metadata: {path}") from exc
        if not isinstance(document, Mapping):
            raise ExtensionLifecycleError(f"lifecycle metadata must be a mapping: {path}")
        return document

    @staticmethod
    def _verify_package(package_path: str | Path, expected_sha256: str | None):
        try:
            return verify_package(package_path, expected_sha256=expected_sha256)
        except ExtensionVerificationError as exc:
            raise ExtensionLifecycleError(str(exc)) from exc

    def _deploy_package(self, package):
        try:
            return deploy_extension(
                package.archive,
                target_root=self.deployment_root,
                expected_sha256=package.sha256,
            )
        except ExtensionDeploymentError as exc:
            raise ExtensionLifecycleError(str(exc)) from exc
