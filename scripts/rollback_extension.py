"""Roll an offline Extension deployment back by switching its active pointer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from scripts.deploy_extension import (  # noqa: E402
    DEFAULT_DEPLOYMENT_ROOT,
    ExtensionDeploymentError,
    _read_json_object,
    activate_version,
)
from scripts.verify_extension import (  # noqa: E402
    ExtensionVerificationError,
    verify_deployment,
)


class ExtensionRollbackError(ValueError):
    """Raised when no verified rollback target can be activated."""


NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, slots=True)
class RollbackResult:
    name: str
    type: str
    from_version: str
    to_version: str
    version_directory: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "version_directory": str(self.version_directory),
        }


def rollback_extension(
    name: str,
    *,
    version: str | None = None,
    target_root: str | Path = DEFAULT_DEPLOYMENT_ROOT,
) -> RollbackResult:
    """Activate an already-installed verified version; never copy or delete code."""

    if NAME_PATTERN.fullmatch(name) is None:
        raise ExtensionRollbackError("Extension name is invalid")
    if version is not None and VERSION_PATTERN.fullmatch(version) is None:
        raise ExtensionRollbackError("rollback version is invalid")
    extension_root = Path(target_root).resolve() / name
    current_path = extension_root / "current.json"
    try:
        current = _read_json_object(current_path)
    except ExtensionDeploymentError as exc:
        raise ExtensionRollbackError(str(exc)) from exc
    if current.get("name") != name or not isinstance(current.get("version"), str):
        raise ExtensionRollbackError(f"invalid current pointer: {current_path}")

    target_version = version or _previous_version(extension_root, str(current["version"]))
    if VERSION_PATTERN.fullmatch(target_version) is None:
        raise ExtensionRollbackError("rollback target version is invalid")
    if target_version == current["version"]:
        raise ExtensionRollbackError("rollback target is already active")
    version_directory = extension_root / "versions" / target_version
    try:
        verified = verify_deployment(version_directory)
    except ExtensionVerificationError as exc:
        raise ExtensionRollbackError(str(exc)) from exc
    if verified.name != name:
        raise ExtensionRollbackError("rollback target belongs to a different Extension")

    try:
        activate_version(
            extension_root,
            name=verified.name,
            extension_type=verified.type,
            version=verified.version,
            package_sha256=verified.package_sha256,
            action="rollback",
        )
    except ExtensionDeploymentError as exc:
        raise ExtensionRollbackError(str(exc)) from exc
    return RollbackResult(
        name=verified.name,
        type=verified.type,
        from_version=str(current["version"]),
        to_version=verified.version,
        version_directory=version_directory,
    )


def _previous_version(extension_root: Path, current_version: str) -> str:
    history = _read_json_object(extension_root / "history.json")
    activations = history.get("activations")
    if not isinstance(activations, list):
        raise ExtensionRollbackError("activation history is invalid")
    for activation in reversed(activations[:-1]):
        if isinstance(activation, dict):
            candidate = activation.get("to_version")
            if isinstance(candidate, str) and candidate != current_version:
                return candidate
    raise ExtensionRollbackError("no previous installed version is available")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Activate a previously installed Extension version offline."
    )
    parser.add_argument("--name", required=True, help="Extension name.")
    parser.add_argument("--version", help="Installed target version (previous by default).")
    parser.add_argument(
        "--target",
        default=str(DEFAULT_DEPLOYMENT_ROOT),
        help="Deployment root (default: workspace/extensions).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = rollback_extension(
        args.name,
        version=args.version,
        target_root=args.target,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
