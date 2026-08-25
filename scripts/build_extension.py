"""Build deterministic, non-executable QwenPaw Extension release packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from core.extensions import (  # noqa: E402
    ExtensionLoader,
    ExtensionMetadata,
    ExtensionRegistry,
    ExtensionType,
)


PACKAGE_SCHEMA_VERSION = "qwenpaw-extension-package.v1"
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)
RELEASE_INFO_NAME = "EXTENSION_RELEASE.json"
GENERATED_CONFIG_TEMPLATE_NAME = "EXTENSION_CONFIG_TEMPLATE.env"
TYPE_DIRECTORIES = {
    ExtensionType.PLUGIN: "plugins",
    ExtensionType.ADAPTER: "adapters",
    ExtensionType.SKILL: "skills",
}

CACHE_DIRECTORIES = {
    "__pycache__",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "cache",
    "node_modules",
}
SENSITIVE_DIRECTORIES = {".secrets", "credentials", "secrets", "tokens"}
IGNORED_DIRECTORIES = CACHE_DIRECTORIES | SENSITIVE_DIRECTORIES | {
    ".git",
    ".idea",
    ".vscode",
}
SECRET_STORE_NAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "credentials.yaml",
    "credentials.yml",
    "secret",
    "secrets",
    "token",
}
IGNORED_SUFFIXES = {
    ".db",
    ".jks",
    ".kdbx",
    ".key",
    ".log",
    ".p12",
    ".pem",
    ".pfx",
    ".pid",
    ".pyc",
    ".pyo",
    ".secret",
    ".sqlite",
    ".sqlite3",
    ".token",
}
TEMPLATE_MARKERS = (".example", ".sample", ".template")


class ExtensionPackagingError(ValueError):
    """Raised when an Extension cannot be packaged safely."""


@dataclass(frozen=True, slots=True)
class PackageResult:
    """Immutable output record for one built package."""

    name: str
    type: str
    version: str
    archive: Path
    sha256: str
    source_file_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "version": self.version,
            "archive": str(self.archive),
            "sha256": self.sha256,
            "source_file_count": self.source_file_count,
        }


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a local file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_filename(metadata: ExtensionMetadata) -> str:
    return f"{metadata.name}-v{metadata.version}.{metadata.type.value}.zip"


def build_extension(
    manifest_path: str | Path,
    output_directory: str | Path,
    *,
    loader: ExtensionLoader | None = None,
) -> PackageResult:
    """Validate and package one Extension directory without executing its code."""

    manifest = Path(manifest_path).resolve()
    extension_root = manifest.parent
    output = Path(output_directory).resolve()
    if output == extension_root or output.is_relative_to(extension_root):
        raise ExtensionPackagingError("output directory cannot be inside the extension")

    extension_loader = loader or ExtensionLoader()
    metadata = extension_loader.load_metadata(manifest)
    expected_directory = TYPE_DIRECTORIES[metadata.type]
    if extension_root.parent.name != expected_directory:
        raise ExtensionPackagingError(
            f"{metadata.type.value} must be stored under {expected_directory}/"
        )
    if extension_root.name != metadata.name:
        raise ExtensionPackagingError(
            "manifest name must match the extension directory name"
        )
    manifest_document = _read_json_object(manifest)
    extension_loader.validate_manifest(
        manifest_document,
        manifest_path=manifest,
        expected_type=metadata.type,
    )

    readme = extension_root / "README.md"
    if not readme.is_file():
        raise ExtensionPackagingError(f"README.md is required: {extension_root}")
    for reserved_name in (RELEASE_INFO_NAME, GENERATED_CONFIG_TEMPLATE_NAME):
        if (extension_root / reserved_name).exists():
            raise ExtensionPackagingError(
                f"{reserved_name} is reserved for generated package metadata"
            )

    source_files = collect_package_files(extension_root)
    relative_names = {path.relative_to(extension_root).as_posix() for path in source_files}
    for required_name in ("manifest.yaml", "README.md"):
        if required_name not in relative_names:
            raise ExtensionPackagingError(f"required package file excluded: {required_name}")

    output.mkdir(parents=True, exist_ok=True)
    archive = output / package_filename(metadata)
    temporary_archive = output / f".{archive.name}.{os.getpid()}.tmp"
    release_info = _release_info(metadata, manifest, len(source_files))

    try:
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as package:
            for source in source_files:
                relative = source.relative_to(extension_root).as_posix()
                _write_source_file(package, source, relative)
            _write_bytes(
                package,
                GENERATED_CONFIG_TEMPLATE_NAME,
                _generated_config_template(manifest_document),
            )
            _write_bytes(
                package,
                RELEASE_INFO_NAME,
                json.dumps(
                    release_info,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ).encode("utf-8")
                + b"\n",
            )
        temporary_archive.replace(archive)
    finally:
        if temporary_archive.exists():
            temporary_archive.unlink()

    digest = sha256_file(archive)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return PackageResult(
        name=metadata.name,
        type=metadata.type.value,
        version=metadata.version,
        archive=archive,
        sha256=digest,
        source_file_count=len(source_files),
    )


def build_all(
    repository_root: str | Path,
    output_directory: str | Path,
    *,
    names: Sequence[str] | None = None,
) -> tuple[PackageResult, ...]:
    """Discover and build all or a selected set of standardized extensions."""

    repository = Path(repository_root).resolve()
    loader = ExtensionLoader(repository / "schemas" / "extension-manifest.schema.json")
    registry = ExtensionRegistry(repository, loader=loader)
    registry.discover()

    selected_names = set(names or ())
    known_names = {metadata.name for metadata in registry.list()}
    unknown_names = sorted(selected_names - known_names)
    if unknown_names:
        raise ExtensionPackagingError(
            f"unknown standardized extensions: {', '.join(unknown_names)}"
        )

    results: list[PackageResult] = []
    for metadata in registry.list():
        if selected_names and metadata.name not in selected_names:
            continue
        manifest = (
            repository
            / TYPE_DIRECTORIES[metadata.type]
            / metadata.name
            / "manifest.yaml"
        )
        results.append(build_extension(manifest, output_directory, loader=loader))

    _write_checksum_index(Path(output_directory).resolve(), results)
    return tuple(results)


def collect_package_files(extension_root: str | Path) -> tuple[Path, ...]:
    """Return stable source files after applying release exclusions."""

    root = Path(extension_root).resolve()
    files: list[Path] = []
    for candidate in root.rglob("*"):
        relative = candidate.relative_to(root)
        if candidate.is_symlink():
            raise ExtensionPackagingError(f"symbolic links are not packaged: {relative}")
        if _excluded(relative):
            continue
        if candidate.is_file():
            files.append(candidate)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def _excluded(relative: Path) -> bool:
    lower_parts = tuple(part.lower() for part in relative.parts)
    if any(part in IGNORED_DIRECTORIES for part in lower_parts[:-1]):
        return True

    name = lower_parts[-1]
    if name in SECRET_STORE_NAMES:
        return True
    if name == ".env" or name.startswith(".env.") or name.endswith(".env"):
        return not any(marker in name for marker in TEMPLATE_MARKERS)
    if name.endswith((".db-wal", ".db-shm", "-wal", "-shm")):
        return True
    return Path(name).suffix.lower() in IGNORED_SUFFIXES


def _release_info(
    metadata: ExtensionMetadata,
    manifest_path: Path,
    source_file_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "name": metadata.name,
        "type": metadata.type.value,
        "version": metadata.version,
        "manifest_sha256": sha256_file(manifest_path),
        "source_file_count": source_file_count,
        "generated_config_template": GENERATED_CONFIG_TEMPLATE_NAME,
    }


def _generated_config_template(manifest: Mapping[str, Any]) -> bytes:
    secret_names = manifest.get("required_secrets", [])
    if not isinstance(secret_names, list):
        raise ExtensionPackagingError("required_secrets must be a list")
    lines = [
        "# Generated from manifest.yaml by qwenpaw-platform.",
        "# Inject values through the deployment secret provider; never commit values.",
    ]
    if secret_names:
        lines.extend(f"{name}=" for name in secret_names)
    else:
        lines.append("# No unconditional secrets are declared by this extension.")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_source_file(package: zipfile.ZipFile, source: Path, target: str) -> None:
    executable = _is_executable_source(source)
    _write_bytes(package, target, source.read_bytes(), executable=executable)


def _write_bytes(
    package: zipfile.ZipFile,
    target: str,
    content: bytes,
    *,
    executable: bool = False,
) -> None:
    normalized = PurePosixPath(target).as_posix()
    info = zipfile.ZipInfo(normalized, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    package.writestr(info, content)


def _is_executable_source(path: Path) -> bool:
    if path.suffix.lower() in {".sh", ".bash"}:
        return True
    try:
        with path.open("rb") as stream:
            return stream.read(2) == b"#!"
    except OSError:
        return False


def _write_checksum_index(
    output_directory: Path,
    results: Iterable[PackageResult],
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    rows = sorted((result.archive.name, result.sha256) for result in results)
    (output_directory / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in rows),
        encoding="utf-8",
    )


def _read_json_object(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    if not isinstance(document, Mapping):
        raise ExtensionPackagingError(f"manifest must contain a mapping: {path}")
    return document


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build validated QwenPaw Extension packages without executing them."
    )
    parser.add_argument(
        "--repository-root",
        default=str(Path.cwd()),
        help="QwenPaw platform repository root (default: current directory).",
    )
    parser.add_argument(
        "--output",
        default="dist/extensions",
        help="Package output directory (default: dist/extensions).",
    )
    parser.add_argument(
        "--extension",
        action="append",
        dest="extensions",
        help="Build one named standardized extension; repeat to select multiple.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    results = build_all(
        args.repository_root,
        args.output,
        names=args.extensions,
    )
    print(
        json.dumps(
            [result.to_dict() for result in results],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
