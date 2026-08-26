"""Generate QwenPaw v2.1 official Plugin manifests from Extension Manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.extensions import ExtensionLoader


PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def build_plugin_manifest(
    extension_manifest_path: str | Path,
    *,
    plugin_id: str,
    name: str,
    description: str,
    permissions: Sequence[str],
    config: Mapping[str, Any],
    plugin_type: str = "general",
    entrypoint: str = "plugin.py",
    manifest_reference: str | None = None,
    adapter_entrypoint: str | None = None,
    config_mapping: Mapping[str, str] | None = None,
    qwenpaw_min_version: str = "2.1.0",
    qwenpaw_max_version: str = "2.2.0",
) -> dict[str, Any]:
    """Return an official Plugin document with wrapper metadata under ``meta``."""

    if not isinstance(plugin_id, str) or PLUGIN_ID_PATTERN.fullmatch(plugin_id) is None:
        raise ValueError("plugin_id must use lowercase kebab-case")
    for value, field_name in (
        (name, "name"),
        (description, "description"),
        (plugin_type, "plugin_type"),
        (entrypoint, "entrypoint"),
        (qwenpaw_min_version, "qwenpaw_min_version"),
        (qwenpaw_max_version, "qwenpaw_max_version"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be non-empty text")
    if isinstance(permissions, (str, bytes)) or not all(
        isinstance(item, str) and item.strip() for item in permissions
    ):
        raise ValueError("permissions must contain only non-empty strings")
    if len(set(permissions)) != len(tuple(permissions)):
        raise ValueError("permissions must be unique")
    if not isinstance(config, Mapping):
        raise TypeError("config must be a mapping")

    manifest_path = Path(extension_manifest_path).resolve()
    metadata = ExtensionLoader().load_metadata(manifest_path)
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_reference = manifest_reference or manifest_path.name
    adapter_entrypoint = adapter_entrypoint or metadata.entrypoint
    extension = {
        "name": metadata.name,
        "type": metadata.type.value,
        "manifest": manifest_reference,
        "runtime": metadata.runtime.value,
        "declared_entrypoint": metadata.entrypoint,
        "adapter_entrypoint": adapter_entrypoint,
    }
    if config_mapping is not None:
        extension["config_mapping"] = dict(config_mapping)
    config_fields = config.get("fields", [])
    required_secrets = (
        [
            field["name"]
            for field in config_fields
            if isinstance(field, Mapping) and field.get("secret") is True
        ]
        if config_mapping is not None
        else list(raw_manifest.get("required_secrets", []))
    )

    return {
        "id": plugin_id,
        "name": name.strip(),
        "version": metadata.version,
        "type": plugin_type.strip(),
        "description": description.strip(),
        "author": "qwenpaw-platform",
        "entry": {"backend": entrypoint.strip()},
        "dependencies": [],
        "qwenpaw_version": {
            "min": qwenpaw_min_version.strip(),
            "max": qwenpaw_max_version.strip(),
        },
        "meta": {
            "extension": extension,
            "permissions": list(permissions),
            "config": dict(config),
            "required_secrets": required_secrets,
        },
    }
