"""Offline parser and validator for Extension Manifests.

This module deliberately does not import an extension entrypoint or start a process.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

from .models import ExtensionMetadata, ExtensionType


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "extension-manifest.schema.json"


class ManifestError(ValueError):
    """Base class for local Manifest failures."""


class MissingManifestError(ManifestError):
    """Raised when a required Extension Manifest is absent."""


class ManifestParseError(ManifestError):
    """Raised when a Manifest is not valid JSON-compatible YAML 1.2."""


class ManifestValidationError(ManifestError):
    """Raised when a parsed Manifest violates the repository specification."""


class ExtensionLoader:
    """Read and validate manifests without loading extension code."""

    def __init__(self, schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> None:
        self.schema_path = Path(schema_path).resolve()
        self._schema = self._read_json_object(
            self.schema_path,
            error_type=ManifestParseError,
            label="Extension Manifest schema",
        )

    def validate_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_path: str | Path | None = None,
        expected_type: ExtensionType | str | None = None,
    ) -> None:
        """Validate structure, values, directory type and declared local paths."""

        if not isinstance(manifest, Mapping):
            raise ManifestValidationError("manifest must be a mapping")

        required = set(self._schema["required"])
        allowed = set(self._schema["properties"])
        missing = sorted(required - set(manifest))
        unknown = sorted(set(manifest) - allowed)
        if missing:
            raise ManifestValidationError(
                f"missing required manifest fields: {', '.join(missing)}"
            )
        if unknown:
            raise ManifestValidationError(
                f"unknown manifest fields: {', '.join(unknown)}"
            )

        self._validate_pattern_field(manifest, "name")
        self._validate_pattern_field(manifest, "version")
        self._require_non_empty_string(manifest["description"], "description")
        self._require_non_empty_string(manifest["entrypoint"], "entrypoint")

        allowed_types = set(self._schema["properties"]["type"]["enum"])
        if not isinstance(manifest["type"], str) or manifest["type"] not in allowed_types:
            raise ManifestValidationError(
                f"unsupported extension type: {manifest['type']}"
            )
        allowed_runtimes = set(self._schema["properties"]["runtime"]["enum"])
        if (
            not isinstance(manifest["runtime"], str)
            or manifest["runtime"] not in allowed_runtimes
        ):
            raise ManifestValidationError(
                f"unsupported extension runtime: {manifest['runtime']}"
            )

        if expected_type is not None:
            try:
                normalized_type = ExtensionType(expected_type)
            except ValueError as exc:
                raise ManifestValidationError(
                    f"unsupported expected extension type: {expected_type}"
                ) from exc
            if manifest["type"] != normalized_type.value:
                raise ManifestValidationError(
                    f"manifest type {manifest['type']} does not match "
                    f"{normalized_type.value} directory"
                )

        self._validate_string_list(manifest["dependencies"], "dependencies")
        self._validate_secret_list(manifest["required_secrets"])
        self._validate_ports(manifest["ports"])
        self._validate_healthcheck(manifest["healthcheck"])

        config_template = manifest["config_template"]
        if config_template is not None:
            self._require_non_empty_string(config_template, "config_template")

        if manifest_path is not None:
            path = Path(manifest_path).resolve()
            if not path.is_file():
                raise MissingManifestError(f"manifest not found: {path}")
            self._validate_declared_path(path.parent, manifest["entrypoint"], "entrypoint")
            if config_template is not None:
                self._validate_declared_path(
                    path.parent,
                    config_template,
                    "config_template",
                )
            healthcheck = manifest["healthcheck"]
            if healthcheck is not None and healthcheck["type"] == "command":
                self._validate_declared_path(
                    path.parent,
                    healthcheck["target"],
                    "healthcheck.target",
                )

    def load_metadata(
        self,
        manifest_path: str | Path,
        *,
        expected_type: ExtensionType | str | None = None,
    ) -> ExtensionMetadata:
        """Parse one Manifest and return its safe metadata projection."""

        path = Path(manifest_path).resolve()
        if not path.is_file():
            raise MissingManifestError(f"manifest not found: {path}")
        manifest = self._read_json_object(
            path,
            error_type=ManifestParseError,
            label="Extension Manifest",
        )
        self.validate_manifest(
            manifest,
            manifest_path=path,
            expected_type=expected_type,
        )
        return ExtensionMetadata(
            name=manifest["name"],
            type=manifest["type"],
            version=manifest["version"],
            runtime=manifest["runtime"],
            entrypoint=manifest["entrypoint"],
            healthcheck=manifest["healthcheck"],
            dependencies=manifest["dependencies"],
        )

    @staticmethod
    def _read_json_object(
        path: Path,
        *,
        error_type: type[ManifestError],
        label: str,
    ) -> dict[str, Any]:
        try:
            with path.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise error_type(
                f"{label} must be readable JSON-compatible YAML 1.2: {path}"
            ) from exc
        if not isinstance(document, dict):
            raise error_type(f"{label} must contain a mapping: {path}")
        return document

    def _validate_pattern_field(self, manifest: Mapping[str, Any], field: str) -> None:
        value = manifest[field]
        self._require_non_empty_string(value, field)
        pattern = self._schema["properties"][field]["pattern"]
        if re.fullmatch(pattern, value) is None:
            raise ManifestValidationError(f"invalid {field}: {value}")

    @staticmethod
    def _require_non_empty_string(value: Any, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ManifestValidationError(f"{field} must be a non-empty string")

    def _validate_string_list(self, value: Any, field: str) -> None:
        if not isinstance(value, list):
            raise ManifestValidationError(f"{field} must be a list")
        for item in value:
            self._require_non_empty_string(item, f"{field} item")
        if len(value) != len(set(value)):
            raise ManifestValidationError(f"{field} must not contain duplicates")

    def _validate_secret_list(self, value: Any) -> None:
        self._validate_string_list(value, "required_secrets")
        pattern = self._schema["properties"]["required_secrets"]["items"]["pattern"]
        if any(re.fullmatch(pattern, item) is None for item in value):
            raise ManifestValidationError(
                "required_secrets must contain uppercase secret identifiers"
            )

    @staticmethod
    def _validate_ports(value: Any) -> None:
        if not isinstance(value, list):
            raise ManifestValidationError("ports must be a list")
        if any(type(port) is not int or not 1 <= port <= 65535 for port in value):
            raise ManifestValidationError("ports must contain integers from 1 to 65535")
        if len(value) != len(set(value)):
            raise ManifestValidationError("ports must not contain duplicates")

    @staticmethod
    def _validate_healthcheck(value: Any) -> None:
        if value is None:
            return
        if not isinstance(value, Mapping) or set(value) != {"type", "target"}:
            raise ManifestValidationError(
                "healthcheck must be null or contain only type and target"
            )
        if value["type"] not in {"http", "command"}:
            raise ManifestValidationError("unsupported healthcheck type")
        if not isinstance(value["target"], str) or not value["target"].strip():
            raise ManifestValidationError("healthcheck.target must be a non-empty string")
        if value["type"] == "http":
            parsed = urlparse(value["target"])
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ManifestValidationError("HTTP healthcheck target must be a valid URL")

    @staticmethod
    def _validate_declared_path(extension_root: Path, value: str, field: str) -> None:
        relative = PurePosixPath(value)
        if relative.is_absolute() or ".." in relative.parts or re.match(r"^[A-Za-z]:", value):
            raise ManifestValidationError(f"{field} must be a safe relative path")
        target = (extension_root / Path(*relative.parts)).resolve()
        if not target.is_relative_to(extension_root.resolve()):
            raise ManifestValidationError(f"{field} escapes the extension directory")
        if not target.is_file():
            raise ManifestValidationError(f"declared {field} does not exist: {target}")
