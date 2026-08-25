"""In-memory registry for validated, non-executable Extension metadata."""

from __future__ import annotations

from pathlib import Path

from .loader import ExtensionLoader, MissingManifestError
from .models import ExtensionMetadata, ExtensionType


class DuplicateExtensionError(ValueError):
    """Raised when two extensions claim the same global name."""


class ExtensionRegistry:
    """Discover and query local manifests without starting extension code."""

    DISCOVERY_ROOTS = (
        ("plugins", ExtensionType.PLUGIN),
        ("adapters", ExtensionType.ADAPTER),
        ("skills", ExtensionType.SKILL),
    )

    def __init__(
        self,
        repository_root: str | Path,
        *,
        loader: ExtensionLoader | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.loader = loader or ExtensionLoader()
        self._extensions: dict[str, ExtensionMetadata] = {}

    def register(self, metadata: ExtensionMetadata) -> None:
        """Register one validated metadata object under a globally unique name."""

        if not isinstance(metadata, ExtensionMetadata):
            raise TypeError("metadata must be an ExtensionMetadata instance")
        if metadata.name in self._extensions:
            raise DuplicateExtensionError(
                f"duplicate extension name: {metadata.name}"
            )
        self._extensions[metadata.name] = metadata

    def discover(self, *, strict: bool = False) -> tuple[ExtensionMetadata, ...]:
        """Scan immediate extension directories and register valid manifests.

        The default compatibility mode skips legacy directories without a Manifest.
        Strict mode reports every missing top-level Manifest before registration.
        """

        discovered: list[ExtensionMetadata] = []
        missing: list[Path] = []

        for root_name, expected_type in self.DISCOVERY_ROOTS:
            root = self.repository_root / root_name
            if not root.is_dir():
                continue
            for extension_dir in sorted(root.iterdir(), key=lambda item: item.name.lower()):
                if not extension_dir.is_dir() or extension_dir.name.startswith(('.', '__')):
                    continue
                manifest_path = extension_dir / "manifest.yaml"
                if not manifest_path.is_file():
                    if strict:
                        missing.append(manifest_path)
                    continue
                discovered.append(
                    self.loader.load_metadata(
                        manifest_path,
                        expected_type=expected_type,
                    )
                )

        if missing:
            rendered = ", ".join(str(path) for path in missing)
            raise MissingManifestError(f"missing extension manifests: {rendered}")

        pending_names: set[str] = set()
        for metadata in discovered:
            if metadata.name in pending_names or metadata.name in self._extensions:
                raise DuplicateExtensionError(
                    f"duplicate extension name: {metadata.name}"
                )
            pending_names.add(metadata.name)

        for metadata in discovered:
            self.register(metadata)
        return tuple(discovered)

    def get(self, name: str) -> ExtensionMetadata | None:
        """Return an extension by name, or None when it is not registered."""

        return self._extensions.get(name)

    def list(
        self,
        extension_type: ExtensionType | str | None = None,
    ) -> tuple[ExtensionMetadata, ...]:
        """Return a stable name-sorted snapshot, optionally filtered by type."""

        normalized_type = (
            ExtensionType(extension_type) if extension_type is not None else None
        )
        values = self._extensions.values()
        if normalized_type is not None:
            values = (
                metadata for metadata in values if metadata.type is normalized_type
            )
        return tuple(sorted(values, key=lambda metadata: metadata.name))
