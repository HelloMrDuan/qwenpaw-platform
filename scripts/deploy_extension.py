"""Install a verified Extension ZIP into a local, versioned workspace simulation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from scripts.build_extension import sha256_file  # noqa: E402
from scripts.verify_extension import (  # noqa: E402
    DEPLOYMENT_RECORD_NAME,
    DEPLOYMENT_SCHEMA_VERSION,
    ExtensionVerificationError,
    PackageVerificationResult,
    validated_zip_entries,
    verify_deployment,
    verify_package,
)


ACTIVE_SCHEMA_VERSION = "qwenpaw-extension-active.v1"
HISTORY_SCHEMA_VERSION = "qwenpaw-extension-history.v1"
DEFAULT_DEPLOYMENT_ROOT = Path("workspace/extensions")


class ExtensionDeploymentError(ValueError):
    """Raised when a verified package cannot be installed safely."""


@dataclass(frozen=True, slots=True)
class DeploymentResult:
    name: str
    type: str
    version: str
    package_sha256: str
    version_directory: Path
    current_pointer: Path
    installed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "version": self.version,
            "package_sha256": self.package_sha256,
            "version_directory": str(self.version_directory),
            "current_pointer": str(self.current_pointer),
            "installed": self.installed,
        }


def deploy_extension(
    package_path: str | Path,
    *,
    target_root: str | Path = DEFAULT_DEPLOYMENT_ROOT,
    expected_sha256: str | None = None,
) -> DeploymentResult:
    """Verify and install one package without importing or starting the Extension."""

    try:
        package = verify_package(package_path, expected_sha256=expected_sha256)
    except ExtensionVerificationError as exc:
        raise ExtensionDeploymentError(str(exc)) from exc

    root = Path(target_root).resolve()
    extension_root = root / package.name
    versions_root = extension_root / "versions"
    version_directory = versions_root / package.version
    versions_root.mkdir(parents=True, exist_ok=True)

    installed = False
    if version_directory.exists():
        existing = _read_json_object(version_directory / DEPLOYMENT_RECORD_NAME)
        if existing.get("package_sha256") != package.sha256:
            raise ExtensionDeploymentError(
                f"version {package.version} is already installed from a different package"
            )
        try:
            verify_deployment(version_directory)
        except ExtensionVerificationError as exc:
            raise ExtensionDeploymentError(str(exc)) from exc
    else:
        _install_to_new_version(package, version_directory)
        installed = True

    activate_version(
        extension_root,
        name=package.name,
        extension_type=package.type,
        version=package.version,
        package_sha256=package.sha256,
        action="install",
    )
    return DeploymentResult(
        name=package.name,
        type=package.type,
        version=package.version,
        package_sha256=package.sha256,
        version_directory=version_directory,
        current_pointer=extension_root / "current.json",
        installed=installed,
    )


def activate_version(
    extension_root: Path,
    *,
    name: str,
    extension_type: str,
    version: str,
    package_sha256: str,
    action: str,
) -> None:
    """Atomically update the non-executable active-version pointer and history."""

    current_path = extension_root / "current.json"
    history_path = extension_root / "history.json"
    previous: Mapping[str, Any] | None = None
    if current_path.is_file():
        previous = _read_json_object(current_path)
        if (
            previous.get("version") == version
            and previous.get("package_sha256") == package_sha256
        ):
            return

    current = {
        "schema_version": ACTIVE_SCHEMA_VERSION,
        "name": name,
        "type": extension_type,
        "version": version,
        "package_sha256": package_sha256,
        "relative_path": f"versions/{version}",
    }
    history: dict[str, Any]
    if history_path.is_file():
        history = dict(_read_json_object(history_path))
        if history.get("schema_version") != HISTORY_SCHEMA_VERSION or not isinstance(
            history.get("activations"), list
        ):
            raise ExtensionDeploymentError(f"invalid activation history: {history_path}")
    else:
        history = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "name": name,
            "activations": [],
        }
    history["activations"].append(
        {
            "action": action,
            "from_version": previous.get("version") if previous else None,
            "to_version": version,
            "package_sha256": package_sha256,
        }
    )
    _atomic_write_json(history_path, history)
    _atomic_write_json(current_path, current)


def _install_to_new_version(
    package: PackageVerificationResult, version_directory: Path
) -> None:
    versions_root = version_directory.parent
    staging = Path(tempfile.mkdtemp(prefix=".deploy-", dir=versions_root))
    try:
        with zipfile.ZipFile(package.archive) as archive:
            entries = validated_zip_entries(archive)
            for relative, info in entries.items():
                target = staging / Path(*PurePosixPath(relative).parts)
                if not target.resolve().is_relative_to(staging.resolve()):
                    raise ExtensionDeploymentError(f"unsafe extraction target: {relative}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
                mode = (info.external_attr >> 16) & 0o777
                if mode:
                    try:
                        os.chmod(target, mode)
                    except OSError:
                        pass

        file_hashes = {
            path.relative_to(staging).as_posix(): sha256_file(path)
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        record = {
            "schema_version": DEPLOYMENT_SCHEMA_VERSION,
            "name": package.name,
            "type": package.type,
            "version": package.version,
            "package_sha256": package.sha256,
            "files": file_hashes,
        }
        _atomic_write_json(staging / DEPLOYMENT_RECORD_NAME, record)
        verify_deployment(staging)
        staging.replace(version_directory)
    except (OSError, zipfile.BadZipFile, ExtensionVerificationError) as exc:
        raise ExtensionDeploymentError(f"Extension installation failed: {exc}") from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _read_json_object(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise ExtensionDeploymentError(f"required deployment metadata missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtensionDeploymentError(f"invalid deployment metadata: {path}") from exc
    if not isinstance(document, Mapping):
        raise ExtensionDeploymentError(f"deployment metadata must be a mapping: {path}")
    return document


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and install an Extension ZIP into an offline workspace."
    )
    parser.add_argument("--package", required=True, help="Extension ZIP to install.")
    parser.add_argument(
        "--target",
        default=str(DEFAULT_DEPLOYMENT_ROOT),
        help="Deployment root (default: workspace/extensions).",
    )
    parser.add_argument("--sha256", help="Expected SHA256 (sidecar used by default).")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = deploy_extension(
        args.package,
        target_root=args.target,
        expected_sha256=args.sha256,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
