"""Verify Extension release packages and offline deployments without executing code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from core.extensions import ExtensionLoader, ExtensionType  # noqa: E402
from scripts.build_extension import (  # noqa: E402
    GENERATED_CONFIG_TEMPLATE_NAME,
    PACKAGE_SCHEMA_VERSION,
    RELEASE_INFO_NAME,
    is_excluded_package_path,
    sha256_file,
)


DEPLOYMENT_RECORD_NAME = "DEPLOYMENT_RECORD.json"
DEPLOYMENT_SCHEMA_VERSION = "qwenpaw-extension-deployment.v1"
MAX_ARCHIVE_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
REQUIRED_PACKAGE_FILES = {
    "manifest.yaml",
    "README.md",
    RELEASE_INFO_NAME,
    GENERATED_CONFIG_TEMPLATE_NAME,
}
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class ExtensionVerificationError(ValueError):
    """Raised when a package or installed version fails offline verification."""


@dataclass(frozen=True, slots=True)
class PackageVerificationResult:
    archive: Path
    name: str
    type: str
    version: str
    sha256: str
    files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive": str(self.archive),
            "name": self.name,
            "type": self.type,
            "version": self.version,
            "sha256": self.sha256,
            "files": list(self.files),
        }


@dataclass(frozen=True, slots=True)
class DeploymentVerificationResult:
    directory: Path
    name: str
    type: str
    version: str
    package_sha256: str
    files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": str(self.directory),
            "name": self.name,
            "type": self.type,
            "version": self.version,
            "package_sha256": self.package_sha256,
            "files": list(self.files),
        }


def verify_package(
    archive_path: str | Path,
    *,
    expected_sha256: str | None = None,
    loader: ExtensionLoader | None = None,
) -> PackageVerificationResult:
    """Validate checksum, structure and metadata of an Extension ZIP."""

    archive = Path(archive_path).resolve()
    if not archive.is_file():
        raise ExtensionVerificationError(f"Extension ZIP not found: {archive}")
    expected = _resolve_expected_sha256(archive, expected_sha256)
    actual = sha256_file(archive)
    if actual.lower() != expected.lower():
        raise ExtensionVerificationError(
            f"SHA256 mismatch for {archive.name}: expected {expected}, got {actual}"
        )

    try:
        with zipfile.ZipFile(archive) as package:
            bad_file = package.testzip()
            if bad_file is not None:
                raise ExtensionVerificationError(
                    f"ZIP integrity check failed at: {bad_file}"
                )
            entries = validated_zip_entries(package)
            file_entries = {name: info for name, info in entries.items() if not info.is_dir()}
            missing = sorted(REQUIRED_PACKAGE_FILES - set(file_entries))
            if missing:
                raise ExtensionVerificationError(
                    f"required package files missing: {', '.join(missing)}"
                )

            manifest_bytes = package.read(file_entries["manifest.yaml"])
            release_bytes = package.read(file_entries[RELEASE_INFO_NAME])
            manifest = _read_json_mapping(manifest_bytes, "manifest.yaml")
            release = _read_json_mapping(release_bytes, RELEASE_INFO_NAME)
            extension_loader = loader or ExtensionLoader()
            extension_loader.validate_manifest(manifest)
            _validate_release_info(release, manifest, manifest_bytes, file_entries)
            _validate_declared_package_paths(manifest, set(file_entries))
            _validate_forbidden_package_paths(set(file_entries))
            _validate_generated_config(
                package.read(file_entries[GENERATED_CONFIG_TEMPLATE_NAME]),
                manifest,
            )
    except zipfile.BadZipFile as exc:
        raise ExtensionVerificationError(f"invalid Extension ZIP: {archive}") from exc

    return PackageVerificationResult(
        archive=archive,
        name=str(manifest["name"]),
        type=str(manifest["type"]),
        version=str(manifest["version"]),
        sha256=actual,
        files=tuple(sorted(file_entries)),
    )


def verify_deployment(
    version_directory: str | Path,
    *,
    loader: ExtensionLoader | None = None,
) -> DeploymentVerificationResult:
    """Verify an extracted, versioned offline deployment against its file record."""

    directory = Path(version_directory).resolve()
    record_path = directory / DEPLOYMENT_RECORD_NAME
    if not directory.is_dir() or not record_path.is_file():
        raise ExtensionVerificationError(
            f"deployment record not found: {record_path}"
        )
    record = _read_json_mapping(record_path.read_bytes(), DEPLOYMENT_RECORD_NAME)
    required_record_fields = {
        "schema_version",
        "name",
        "type",
        "version",
        "package_sha256",
        "files",
    }
    if set(record) != required_record_fields:
        raise ExtensionVerificationError("deployment record fields are invalid")
    if record["schema_version"] != DEPLOYMENT_SCHEMA_VERSION:
        raise ExtensionVerificationError("unsupported deployment record schema")
    if record["type"] not in {item.value for item in ExtensionType}:
        raise ExtensionVerificationError("deployment record type is invalid")
    if not isinstance(record["files"], Mapping) or not record["files"]:
        raise ExtensionVerificationError("deployment record files must be a mapping")
    if not _valid_sha256(record["package_sha256"]):
        raise ExtensionVerificationError("deployment package_sha256 is invalid")

    recorded_files = dict(record["files"])
    actual_files = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != record_path
    }
    if actual_files != set(recorded_files):
        missing = sorted(set(recorded_files) - actual_files)
        extra = sorted(actual_files - set(recorded_files))
        raise ExtensionVerificationError(
            f"deployment file set mismatch; missing={missing}, extra={extra}"
        )
    _validate_forbidden_package_paths(actual_files)
    for relative, expected_digest in recorded_files.items():
        if not isinstance(relative, str) or not _valid_sha256(expected_digest):
            raise ExtensionVerificationError("deployment file hash record is invalid")
        actual_digest = sha256_file(directory / Path(*PurePosixPath(relative).parts))
        if actual_digest != expected_digest.lower():
            raise ExtensionVerificationError(f"deployed file hash mismatch: {relative}")

    manifest = _read_json_mapping(
        (directory / "manifest.yaml").read_bytes(), "manifest.yaml"
    )
    extension_loader = loader or ExtensionLoader()
    extension_loader.validate_manifest(
        manifest,
        manifest_path=directory / "manifest.yaml",
        expected_type=str(record["type"]),
    )
    release = _read_json_mapping(
        (directory / RELEASE_INFO_NAME).read_bytes(), RELEASE_INFO_NAME
    )
    for field in ("name", "type", "version"):
        if manifest[field] != record[field] or release[field] != record[field]:
            raise ExtensionVerificationError(
                f"deployed {field} is inconsistent across metadata"
            )

    return DeploymentVerificationResult(
        directory=directory,
        name=str(record["name"]),
        type=str(record["type"]),
        version=str(record["version"]),
        package_sha256=str(record["package_sha256"]),
        files=tuple(sorted(actual_files)),
    )


def validated_zip_entries(package: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Return normalized, safe ZIP entries or raise a verification error."""

    infos = package.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ExtensionVerificationError("ZIP contains too many entries")
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        raise ExtensionVerificationError("ZIP uncompressed size exceeds safety limit")

    entries: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        if info.flag_bits & 0x1:
            raise ExtensionVerificationError(f"encrypted ZIP entry is not allowed: {info.filename}")
        if "\\" in info.filename:
            raise ExtensionVerificationError(f"backslash ZIP path is not allowed: {info.filename}")
        path = PurePosixPath(info.filename)
        normalized = path.as_posix().rstrip("/")
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or re.match(r"^[A-Za-z]:", normalized)
        ):
            raise ExtensionVerificationError(f"unsafe ZIP path: {info.filename}")
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise ExtensionVerificationError(f"symbolic link ZIP entry is not allowed: {normalized}")
        if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ExtensionVerificationError(f"non-file ZIP entry is not allowed: {normalized}")
        if normalized in entries:
            raise ExtensionVerificationError(f"duplicate ZIP path: {normalized}")
        entries[normalized] = info
    return entries


def _resolve_expected_sha256(archive: Path, value: str | None) -> str:
    if value is not None:
        expected = value.strip().lower()
    else:
        sidecar = archive.with_suffix(archive.suffix + ".sha256")
        if not sidecar.is_file():
            raise ExtensionVerificationError(
                "expected SHA256 is required when the .zip.sha256 sidecar is absent"
            )
        parts = sidecar.read_text(encoding="utf-8").strip().split()
        if len(parts) != 2 or parts[1] != archive.name:
            raise ExtensionVerificationError(f"invalid SHA256 sidecar: {sidecar}")
        expected = parts[0].lower()
    if not _valid_sha256(expected):
        raise ExtensionVerificationError("expected SHA256 must contain 64 hex characters")
    return expected


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _read_json_mapping(content: bytes, label: str) -> Mapping[str, Any]:
    try:
        document = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionVerificationError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(document, Mapping):
        raise ExtensionVerificationError(f"{label} must contain a mapping")
    return document


def _validate_release_info(
    release: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_bytes: bytes,
    file_entries: Mapping[str, zipfile.ZipInfo],
) -> None:
    expected_fields = {
        "schema_version",
        "name",
        "type",
        "version",
        "manifest_sha256",
        "source_file_count",
        "generated_config_template",
    }
    if set(release) != expected_fields:
        raise ExtensionVerificationError("Extension release metadata fields are invalid")
    if release["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise ExtensionVerificationError("unsupported Extension package schema")
    for field in ("name", "type", "version"):
        if release[field] != manifest[field]:
            raise ExtensionVerificationError(f"release {field} does not match manifest")
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if release["manifest_sha256"] != manifest_digest:
        raise ExtensionVerificationError("release manifest SHA256 does not match")
    if release["generated_config_template"] != GENERATED_CONFIG_TEMPLATE_NAME:
        raise ExtensionVerificationError("generated config template name is inconsistent")
    source_count = len(file_entries) - 2
    if type(release["source_file_count"]) is not int or release["source_file_count"] != source_count:
        raise ExtensionVerificationError("release source file count is inconsistent")


def _validate_declared_package_paths(
    manifest: Mapping[str, Any], names: set[str]
) -> None:
    declared: list[tuple[str, str]] = []
    if manifest["type"] == ExtensionType.SKILL.value:
        declared.append(("executor.path", manifest["executor"]["path"]))
        declared.extend(
            (f"schemas.{key}", value) for key, value in manifest["schemas"].items()
        )
        declared.extend(("tests item", value) for value in manifest["tests"])
    else:
        declared.append(("entrypoint", manifest["entrypoint"]))
        if manifest["config_template"] is not None:
            declared.append(("config_template", manifest["config_template"]))
        healthcheck = manifest["healthcheck"]
        if healthcheck is not None and healthcheck["type"] == "command":
            declared.append(("healthcheck.target", healthcheck["target"]))
    for label, value in declared:
        if PurePosixPath(value).as_posix() not in names:
            raise ExtensionVerificationError(
                f"declared {label} is absent from package: {value}"
            )


def _validate_forbidden_package_paths(names: set[str]) -> None:
    generated = {RELEASE_INFO_NAME, GENERATED_CONFIG_TEMPLATE_NAME}
    forbidden = sorted(
        name
        for name in names
        if name not in generated
        and is_excluded_package_path(Path(*PurePosixPath(name).parts))
    )
    if forbidden:
        raise ExtensionVerificationError(
            f"forbidden runtime or secret files included: {', '.join(forbidden)}"
        )


def _validate_generated_config(content: bytes, manifest: Mapping[str, Any]) -> None:
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ExtensionVerificationError("generated config must be UTF-8") from exc
    declared = set(manifest.get("required_secrets", []))
    found: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ExtensionVerificationError("generated config contains an invalid line")
        key, value = stripped.split("=", 1)
        if value:
            raise ExtensionVerificationError("generated config contains a secret value")
        found.add(key)
    if found != declared:
        raise ExtensionVerificationError("generated config keys do not match required_secrets")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an Extension ZIP or deployment.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--package", help="Extension ZIP to verify.")
    target.add_argument("--deployment", help="Installed version directory to verify.")
    parser.add_argument("--sha256", help="Expected package SHA256 (sidecar used by default).")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.package:
        result = verify_package(args.package, expected_sha256=args.sha256)
    else:
        if args.sha256:
            raise ExtensionVerificationError("--sha256 only applies to --package")
        result = verify_deployment(args.deployment)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
