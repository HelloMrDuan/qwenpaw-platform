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

COMMON_FIELDS = {"name", "type", "version", "description"}
RUNTIME_EXTENSION_FIELDS = COMMON_FIELDS | {
    "runtime",
    "entrypoint",
    "dependencies",
    "config_template",
    "healthcheck",
    "ports",
    "required_secrets",
}
SKILL_EXTENSION_FIELDS = COMMON_FIELDS | {
    "executor",
    "dependencies",
    "schemas",
    "artifacts",
    "events",
    "tests",
}


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

        missing_common = sorted(COMMON_FIELDS - set(manifest))
        if missing_common:
            raise ManifestValidationError(
                f"missing required manifest fields: {', '.join(missing_common)}"
            )

        self._validate_pattern_field(manifest, "name")
        self._validate_pattern_field(manifest, "version")
        self._require_non_empty_string(manifest["description"], "description")

        allowed_types = set(self._schema["properties"]["type"]["enum"])
        manifest_type = manifest["type"]
        if not isinstance(manifest_type, str) or manifest_type not in allowed_types:
            raise ManifestValidationError(
                f"unsupported extension type: {manifest_type}"
            )

        allowed_fields = (
            SKILL_EXTENSION_FIELDS
            if manifest_type == ExtensionType.SKILL.value
            else RUNTIME_EXTENSION_FIELDS
        )
        missing = sorted(allowed_fields - set(manifest))
        unknown = sorted(set(manifest) - allowed_fields)
        if missing:
            raise ManifestValidationError(
                f"missing required manifest fields: {', '.join(missing)}"
            )
        if unknown:
            raise ManifestValidationError(
                f"fields are not valid for {manifest_type}: {', '.join(unknown)}"
            )

        if expected_type is not None:
            try:
                normalized_type = ExtensionType(expected_type)
            except ValueError as exc:
                raise ManifestValidationError(
                    f"unsupported expected extension type: {expected_type}"
                ) from exc
            if manifest_type != normalized_type.value:
                raise ManifestValidationError(
                    f"manifest type {manifest_type} does not match "
                    f"{normalized_type.value} directory"
                )

        if manifest_type == ExtensionType.SKILL.value:
            self._validate_skill_manifest(manifest, manifest_path=manifest_path)
        else:
            self._validate_runtime_manifest(manifest, manifest_path=manifest_path)

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

        if manifest["type"] == ExtensionType.SKILL.value:
            executor = manifest["executor"]
            return ExtensionMetadata(
                name=manifest["name"],
                type=manifest["type"],
                version=manifest["version"],
                runtime=executor["runtime"],
                entrypoint=executor["path"],
                healthcheck=None,
                dependencies=manifest["dependencies"],
                executor=executor,
                schemas=manifest["schemas"],
                artifacts=manifest["artifacts"],
                events=manifest["events"],
                tests=manifest["tests"],
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

    def _validate_runtime_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_path: str | Path | None,
    ) -> None:
        allowed_runtimes = set(self._schema["properties"]["runtime"]["enum"])
        if (
            not isinstance(manifest["runtime"], str)
            or manifest["runtime"] not in allowed_runtimes
        ):
            raise ManifestValidationError(
                f"unsupported extension runtime: {manifest['runtime']}"
            )

        self._validate_relative_path_value(manifest["entrypoint"], "entrypoint")
        self._validate_string_list(manifest["dependencies"], "dependencies")
        self._validate_secret_list(manifest["required_secrets"])
        self._validate_ports(manifest["ports"])
        self._validate_healthcheck(manifest["healthcheck"])

        config_template = manifest["config_template"]
        if config_template is not None:
            self._validate_relative_path_value(config_template, "config_template")

        path = self._existing_manifest_path(manifest_path)
        if path is None:
            return
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

    def _validate_skill_manifest(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_path: str | Path | None,
    ) -> None:
        self._validate_string_list(manifest["dependencies"], "dependencies")
        self._validate_executor(manifest["executor"])
        self._validate_schemas(manifest["schemas"])
        self._validate_artifacts(manifest["artifacts"])

        allowed_events = set(self._schema["properties"]["events"]["items"]["enum"])
        self._validate_string_list(manifest["events"], "events", require_items=True)
        invalid_events = sorted(set(manifest["events"]) - allowed_events)
        if invalid_events:
            raise ManifestValidationError(
                f"unsupported Skill events: {', '.join(invalid_events)}"
            )

        self._validate_string_list(manifest["tests"], "tests", require_items=True)
        for test_path in manifest["tests"]:
            self._validate_relative_path_value(test_path, "tests item")

        path = self._existing_manifest_path(manifest_path)
        if path is None:
            return
        self._validate_declared_path(
            path.parent,
            manifest["executor"]["path"],
            "executor.path",
        )
        for schema_name, schema_path in manifest["schemas"].items():
            self._validate_declared_path(
                path.parent,
                schema_path,
                f"schemas.{schema_name}",
            )
        for test_path in manifest["tests"]:
            self._validate_declared_path(path.parent, test_path, "tests item")

    def _validate_executor(self, value: Any) -> None:
        if not isinstance(value, Mapping) or set(value) != {
            "runtime",
            "path",
            "callable",
        }:
            raise ManifestValidationError(
                "executor must contain only runtime, path, and callable"
            )
        allowed_runtimes = set(self._schema["properties"]["runtime"]["enum"])
        if not isinstance(value["runtime"], str) or value["runtime"] not in allowed_runtimes:
            raise ManifestValidationError("unsupported executor runtime")
        self._validate_relative_path_value(value["path"], "executor.path")
        callable_pattern = self._schema["properties"]["executor"]["properties"][
            "callable"
        ]["pattern"]
        if (
            not isinstance(value["callable"], str)
            or re.fullmatch(callable_pattern, value["callable"]) is None
        ):
            raise ManifestValidationError("executor.callable must be a Python-style name")

    def _validate_schemas(self, value: Any) -> None:
        if not isinstance(value, Mapping) or set(value) != {"request", "result"}:
            raise ManifestValidationError(
                "schemas must contain only request and result paths"
            )
        for schema_name, schema_path in value.items():
            self._validate_relative_path_value(schema_path, f"schemas.{schema_name}")

    def _validate_artifacts(self, value: Any) -> None:
        if not isinstance(value, Mapping) or set(value) != {
            "inputs",
            "outputs",
            "uri_scheme",
        }:
            raise ManifestValidationError(
                "artifacts must contain inputs, outputs, and uri_scheme"
            )
        if value["uri_scheme"] != "artifact":
            raise ManifestValidationError("artifacts.uri_scheme must be artifact")
        for direction in ("inputs", "outputs"):
            declarations = value[direction]
            if not isinstance(declarations, list) or not declarations:
                raise ManifestValidationError(
                    f"artifacts.{direction} must be a non-empty list"
                )
            names: list[str] = []
            for declaration in declarations:
                self._validate_artifact_declaration(declaration, direction)
                names.append(declaration["name"])
            if len(names) != len(set(names)):
                raise ManifestValidationError(
                    f"artifacts.{direction} names must be unique"
                )

    def _validate_artifact_declaration(self, value: Any, direction: str) -> None:
        if not isinstance(value, Mapping) or set(value) != {
            "name",
            "kind",
            "mime_types",
            "required",
        }:
            raise ManifestValidationError(
                f"artifacts.{direction} declarations require name, kind, mime_types, required"
            )
        artifact_schema = self._schema["$defs"]["artifactDeclaration"]
        name_pattern = artifact_schema["properties"]["name"]["pattern"]
        if not isinstance(value["name"], str) or re.fullmatch(name_pattern, value["name"]) is None:
            raise ManifestValidationError("artifact declaration name is invalid")
        allowed_kinds = set(artifact_schema["properties"]["kind"]["enum"])
        if not isinstance(value["kind"], str) or value["kind"] not in allowed_kinds:
            raise ManifestValidationError("artifact declaration kind is invalid")
        self._validate_string_list(value["mime_types"], "mime_types", require_items=True)
        mime_pattern = artifact_schema["properties"]["mime_types"]["items"]["pattern"]
        if any(re.fullmatch(mime_pattern, item) is None for item in value["mime_types"]):
            raise ManifestValidationError("artifact declaration MIME type is invalid")
        if type(value["required"]) is not bool:
            raise ManifestValidationError("artifact declaration required must be boolean")

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
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
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

    def _validate_relative_path_value(self, value: Any, field: str) -> None:
        self._require_non_empty_string(value, field)
        pattern = self._schema["$defs"]["relativePath"]["pattern"]
        if re.fullmatch(pattern, value) is None:
            raise ManifestValidationError(f"{field} must be a safe relative path")

    def _validate_string_list(
        self,
        value: Any,
        field: str,
        *,
        require_items: bool = False,
    ) -> None:
        if not isinstance(value, list):
            raise ManifestValidationError(f"{field} must be a list")
        if require_items and not value:
            raise ManifestValidationError(f"{field} must not be empty")
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
        if not isinstance(value["type"], str) or value["type"] not in {
            "http",
            "command",
        }:
            raise ManifestValidationError("unsupported healthcheck type")
        if not isinstance(value["target"], str) or not value["target"].strip():
            raise ManifestValidationError("healthcheck.target must be a non-empty string")
        if value["type"] == "http":
            parsed = urlparse(value["target"])
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ManifestValidationError("HTTP healthcheck target must be a valid URL")

    @staticmethod
    def _existing_manifest_path(value: str | Path | None) -> Path | None:
        if value is None:
            return None
        path = Path(value).resolve()
        if not path.is_file():
            raise MissingManifestError(f"manifest not found: {path}")
        return path

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
