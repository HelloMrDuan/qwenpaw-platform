"""Offline AgentScope Workspace adapter for verified Extension release ZIPs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping
import zipfile

from core.extensions import ExtensionLoader, ExtensionType
from scripts.verify_extension import ExtensionVerificationError, verify_package

from .models import (
    ExtensionPackageDescriptor,
    InstallAction,
    InstallPlan,
    InstallPlanStep,
    RollbackAction,
    RollbackPlan,
    RollbackPlanStep,
    SecretRequirementCheck,
)
from .workspace_mapper import WorkspaceMapper


class AgentScopeDeploymentBridgeError(ValueError):
    """Raised when an offline AgentScope Workspace plan cannot be produced."""


class AgentScopeDeploymentAdapter:
    """Parse release packages and build plans without changing a Workspace."""

    def __init__(
        self,
        *,
        loader: ExtensionLoader | None = None,
        workspace_mapper: WorkspaceMapper | None = None,
    ) -> None:
        self.loader = loader or ExtensionLoader()
        self.workspace_mapper = workspace_mapper or WorkspaceMapper()

    def parse_package(
        self,
        archive_path: str | Path,
        *,
        expected_sha256: str | None = None,
    ) -> ExtensionPackageDescriptor:
        try:
            verified = verify_package(
                archive_path,
                expected_sha256=expected_sha256,
                loader=self.loader,
            )
            manifest = self._read_manifest(verified.archive)
            self.loader.validate_manifest(manifest)
        except (ExtensionVerificationError, OSError, ValueError, zipfile.BadZipFile) as exc:
            raise AgentScopeDeploymentBridgeError(str(exc)) from exc

        if (
            manifest.get("name") != verified.name
            or manifest.get("type") != verified.type
            or manifest.get("version") != verified.version
        ):
            raise AgentScopeDeploymentBridgeError(
                "verified package identity differs from its Manifest"
            )
        required_secrets = (
            manifest.get("required_secrets", [])
            if verified.type != ExtensionType.SKILL.value
            else []
        )
        if not isinstance(required_secrets, list):
            raise AgentScopeDeploymentBridgeError(
                "Manifest required_secrets must be a list"
            )
        return ExtensionPackageDescriptor(
            archive=verified.archive,
            name=verified.name,
            type=verified.type,
            version=verified.version,
            sha256=verified.sha256,
            files=verified.files,
            required_secrets=tuple(required_secrets),
        )

    def create_install_plan(
        self,
        archive_path: str | Path,
        workspace_root: str | Path,
        *,
        available_secrets: Iterable[str] = (),
        expected_sha256: str | None = None,
    ) -> InstallPlan:
        package = self.parse_package(
            archive_path,
            expected_sha256=expected_sha256,
        )
        mapping = self.workspace_mapper.map_package(package, workspace_root)
        secrets = self.check_secrets(package, available_secrets)
        plan_identity = "|".join(
            (
                package.sha256,
                str(mapping.workspace_root),
                mapping.relative_target,
            )
        )
        plan_id = "plan_" + hashlib.sha256(plan_identity.encode("utf-8")).hexdigest()[:24]
        steps = (
            InstallPlanStep(1, InstallAction.VERIFY_PACKAGE, str(package.archive)),
            InstallPlanStep(
                2,
                InstallAction.CHECK_SECRETS,
                f"secret-requirements://{package.name}",
            ),
            InstallPlanStep(
                3,
                InstallAction.PREPARE_TARGET,
                str(mapping.target_directory),
            ),
            InstallPlanStep(
                4,
                InstallAction.INSTALL_PAYLOAD,
                str(mapping.target_directory),
            ),
            InstallPlanStep(
                5,
                InstallAction.VERIFY_WORKSPACE,
                str(mapping.target_directory),
            ),
        )
        return InstallPlan(
            plan_id=plan_id,
            package=package,
            mapping=mapping,
            secrets=secrets,
            steps=steps,
        )

    def create_rollback_plan(
        self,
        current_archive: str | Path,
        rollback_archive: str | Path,
        workspace_root: str | Path,
        *,
        available_secrets: Iterable[str] = (),
        expected_current_sha256: str | None = None,
        expected_rollback_sha256: str | None = None,
    ) -> RollbackPlan:
        current = self.parse_package(
            current_archive,
            expected_sha256=expected_current_sha256,
        )
        rollback = self.parse_package(
            rollback_archive,
            expected_sha256=expected_rollback_sha256,
        )
        if current.name != rollback.name or current.type is not rollback.type:
            raise AgentScopeDeploymentBridgeError(
                "rollback packages must describe one Extension identity"
            )
        if current.version == rollback.version:
            raise AgentScopeDeploymentBridgeError(
                "rollback package must use a different version"
            )
        mapping = self.workspace_mapper.map_package(rollback, workspace_root)
        secrets = self.check_secrets(rollback, available_secrets)
        identity = "|".join(
            (
                current.sha256,
                rollback.sha256,
                str(mapping.workspace_root),
                mapping.relative_target,
            )
        )
        plan_id = (
            "rollback_"
            + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        )
        steps = (
            RollbackPlanStep(
                1,
                RollbackAction.VERIFY_ROLLBACK_PACKAGE,
                str(rollback.archive),
            ),
            RollbackPlanStep(
                2,
                RollbackAction.CHECK_SECRETS,
                f"secret-requirements://{rollback.name}/{rollback.version}",
            ),
            RollbackPlanStep(
                3,
                RollbackAction.PRESERVE_CURRENT_TARGET,
                str(mapping.target_directory),
            ),
            RollbackPlanStep(
                4,
                RollbackAction.RESTORE_PAYLOAD,
                str(mapping.target_directory),
            ),
            RollbackPlanStep(
                5,
                RollbackAction.VERIFY_WORKSPACE,
                str(mapping.target_directory),
            ),
        )
        return RollbackPlan(
            plan_id=plan_id,
            current_package=current,
            rollback_package=rollback,
            mapping=mapping,
            secrets=secrets,
            steps=steps,
        )

    @staticmethod
    def check_secrets(
        package: ExtensionPackageDescriptor,
        available_secrets: Iterable[str],
    ) -> SecretRequirementCheck:
        if not isinstance(package, ExtensionPackageDescriptor):
            raise TypeError("package must be an ExtensionPackageDescriptor")
        if isinstance(available_secrets, Mapping) or isinstance(
            available_secrets, (str, bytes)
        ):
            raise TypeError(
                "available_secrets must contain names only, never a value mapping"
            )
        available_names = tuple(available_secrets)
        if not all(isinstance(name, str) and name.strip() for name in available_names):
            raise ValueError("available secret names must be non-empty strings")
        required = set(package.required_secrets)
        satisfied = required.intersection(available_names)
        missing = required - satisfied
        return SecretRequirementCheck(
            required=tuple(required),
            available=tuple(satisfied),
            missing=tuple(missing),
        )

    @staticmethod
    def _read_manifest(archive: Path) -> Mapping[str, object]:
        with zipfile.ZipFile(archive) as package:
            document = json.loads(package.read("manifest.yaml").decode("utf-8"))
        if not isinstance(document, Mapping):
            raise AgentScopeDeploymentBridgeError(
                "Extension package Manifest must contain a mapping"
            )
        return document
