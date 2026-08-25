"""Local health evaluation based only on deployed-file integrity and state."""

from __future__ import annotations

from pathlib import Path

from scripts.verify_extension import ExtensionVerificationError, verify_deployment

from .models import ExtensionState, HealthReport, LifecycleRecord


class LocalHealthChecker:
    """Check a deployment without importing, starting or probing its entrypoint."""

    def check(self, record: LifecycleRecord, version_directory: Path) -> HealthReport:
        try:
            verified = verify_deployment(version_directory)
        except ExtensionVerificationError as exc:
            return HealthReport(
                name=record.name,
                version=record.version,
                state=ExtensionState.FAILED,
                healthy=False,
                deployment_verified=False,
                runtime_probe_performed=False,
                code="DEPLOYMENT_INVALID",
                message=str(exc),
            )
        if (
            verified.name != record.name
            or verified.type != record.type.value
            or verified.version != record.version
            or verified.package_sha256 != record.package_sha256
        ):
            return HealthReport(
                name=record.name,
                version=record.version,
                state=ExtensionState.FAILED,
                healthy=False,
                deployment_verified=False,
                runtime_probe_performed=False,
                code="LIFECYCLE_METADATA_MISMATCH",
                message="lifecycle metadata does not match the active deployment",
            )

        if record.state is ExtensionState.DISABLED:
            return HealthReport(
                name=record.name,
                version=record.version,
                state=record.state,
                healthy=False,
                deployment_verified=True,
                runtime_probe_performed=False,
                code="DISABLED",
                message="Extension is disabled; package integrity is valid",
            )
        if record.state is ExtensionState.FAILED:
            return HealthReport(
                name=record.name,
                version=record.version,
                state=record.state,
                healthy=False,
                deployment_verified=True,
                runtime_probe_performed=False,
                code="LIFECYCLE_FAILED",
                message=record.error or "Extension lifecycle is marked failed",
            )

        code = {
            ExtensionState.INSTALLED: "VERIFIED_INSTALLED",
            ExtensionState.ENABLED: "VERIFIED_ENABLED",
            ExtensionState.RUNNING: "SIMULATED_RUNNING",
        }[record.state]
        return HealthReport(
            name=record.name,
            version=record.version,
            state=record.state,
            healthy=True,
            deployment_verified=True,
            runtime_probe_performed=False,
            code=code,
            message=(
                "Local package integrity is valid; no Runtime process probe was performed"
            ),
        )
