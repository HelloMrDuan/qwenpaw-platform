"""Pure AgentScope Workspace target mapping for verified Extension packages."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from core.extensions import ExtensionType

from .models import ExtensionPackageDescriptor, WorkspaceMapping


TYPE_TARGET_ROOTS = {
    ExtensionType.SKILL: PurePosixPath("skills"),
    ExtensionType.PLUGIN: PurePosixPath("extensions/plugins"),
    ExtensionType.ADAPTER: PurePosixPath("extensions/adapters"),
}


class WorkspaceMappingError(ValueError):
    """Raised when an Extension cannot be mapped safely into a Workspace."""


class WorkspaceMapper:
    """Generate logical target paths without creating or modifying directories."""

    def map_package(
        self,
        package: ExtensionPackageDescriptor,
        workspace_root: str | Path,
    ) -> WorkspaceMapping:
        if not isinstance(package, ExtensionPackageDescriptor):
            raise TypeError("package must be an ExtensionPackageDescriptor")
        root = Path(workspace_root).resolve()
        target_root = TYPE_TARGET_ROOTS.get(package.type)
        if target_root is None:
            raise WorkspaceMappingError(
                f"unsupported Extension mapping type: {package.type}"
            )
        relative = target_root / package.name
        return WorkspaceMapping(
            extension_name=package.name,
            extension_type=package.type,
            workspace_root=root,
            relative_target=relative.as_posix(),
        )

    def map_packages(
        self,
        packages: Iterable[ExtensionPackageDescriptor],
        workspace_root: str | Path,
    ) -> tuple[WorkspaceMapping, ...]:
        mappings = tuple(
            self.map_package(package, workspace_root) for package in packages
        )
        targets = [mapping.relative_target for mapping in mappings]
        if len(set(targets)) != len(targets):
            raise WorkspaceMappingError("multiple packages map to one Workspace target")
        return mappings
