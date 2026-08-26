"""Build deterministic, non-executable QwenPaw Extension release packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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

QWENPAW_PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
QWENPAW_PLUGIN_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
QWENPAW_PLUGIN_SHARED_CORE_ROOTS = (
    "core/contracts",
    "core/extensions",
    "core/streaming",
)
QWENPAW_PLUGIN_SCRIPT_DEPENDENCIES = (
    "scripts/build_extension.py",
    "scripts/deploy_extension.py",
    "scripts/rollback_extension.py",
    "scripts/verify_extension.py",
)


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


def build_qwenpaw_plugin(
    plugin_directory: str | Path,
    output_directory: str | Path,
    *,
    repository_root: str | Path | None = None,
) -> PackageResult:
    """Build one self-contained official QwenPaw backend Plugin ZIP.

    Provider behavior is not rewritten or executed.  The builder assembles the
    existing Plugin facade, Adapter, Runtime wrapper, contract/runtime closure,
    and validated internal Extension metadata under the Plugin archive root.
    """

    plugin_root = Path(plugin_directory).resolve()
    repository = (
        Path(repository_root).resolve()
        if repository_root is not None
        else plugin_root.parents[1]
    )
    output = Path(output_directory).resolve()
    if output == plugin_root or output.is_relative_to(plugin_root):
        raise ExtensionPackagingError("output directory cannot be inside the Plugin")
    if plugin_root.parent != repository / "plugins":
        raise ExtensionPackagingError(
            "official Plugin facade must be stored directly under plugins/"
        )

    plugin_manifest_path = plugin_root / "plugin.json"
    plugin_manifest = _read_json_object(plugin_manifest_path)
    identity = _validate_qwenpaw_plugin_manifest(
        plugin_manifest,
        plugin_root=plugin_root,
        repository_root=repository,
    )
    internal_manifest_path = identity["internal_manifest_path"]
    adapter_source_path = identity["adapter_source_path"]
    internal_metadata = identity["internal_metadata"]
    adapter_relative = PurePosixPath(
        str(plugin_manifest["meta"]["extension"]["adapter_entrypoint"])
    )
    packaged_adapter_relative = PurePosixPath("adapter", *adapter_relative.parts[1:])
    package_namespace = _qwenpaw_plugin_namespace(str(plugin_manifest["id"]))

    sources: dict[str, Path] = {}

    def add_source(target: str, source: Path) -> None:
        normalized = PurePosixPath(target).as_posix()
        if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
            raise ExtensionPackagingError(f"unsafe Plugin package target: {target}")
        source = source.resolve()
        if not source.is_file():
            raise ExtensionPackagingError(f"Plugin dependency is missing: {source}")
        existing = sources.get(normalized)
        if existing is not None and existing != source:
            raise ExtensionPackagingError(
                f"Plugin dependency target collision: {normalized}"
            )
        sources[normalized] = source

    for source in collect_package_files(plugin_root):
        relative = source.relative_to(plugin_root).as_posix()
        if relative not in {"plugin.json", "plugin.py"}:
            add_source(relative, source)

    for source_root_name in QWENPAW_PLUGIN_SHARED_CORE_ROOTS:
        source_root = repository / Path(*PurePosixPath(source_root_name).parts)
        if not source_root.is_dir():
            raise ExtensionPackagingError(
                f"shared Plugin runtime directory is missing: {source_root}"
            )
        for source in collect_package_files(source_root):
            add_source(source.relative_to(repository).as_posix(), source)

    for script_name in QWENPAW_PLUGIN_SCRIPT_DEPENDENCIES:
        add_source(script_name, repository / Path(*PurePosixPath(script_name).parts))

    add_source(
        "schemas/extension-manifest.schema.json",
        repository / "schemas" / "extension-manifest.schema.json",
    )
    add_source(
        "runtime/wrapper.py",
        repository / "plugins" / "runtime-wrapper" / "runtime.py",
    )

    add_source(packaged_adapter_relative.as_posix(), adapter_source_path)

    contracts_root = repository / "core" / "contracts"
    for source in collect_package_files(contracts_root):
        add_source(
            PurePosixPath(
                "contracts",
                *source.relative_to(contracts_root).parts,
            ).as_posix(),
            source,
        )

    internal_manifest_relative = internal_manifest_path.relative_to(repository)
    add_source(internal_manifest_relative.as_posix(), internal_manifest_path)
    internal_document = _read_json_object(internal_manifest_path)
    internal_entrypoint = _safe_relative_path(
        internal_document["entrypoint"],
        "internal manifest entrypoint",
    )
    add_source(
        PurePosixPath(
            *internal_manifest_relative.parent.parts,
            *internal_entrypoint.parts,
        ).as_posix(),
        internal_manifest_path.parent / Path(*internal_entrypoint.parts),
    )
    config_template = internal_document.get("config_template")
    if config_template is not None:
        config_relative = _safe_relative_path(
            config_template,
            "internal manifest config_template",
        )
        add_source(
            PurePosixPath(
                *internal_manifest_relative.parent.parts,
                *config_relative.parts,
            ).as_posix(),
            internal_manifest_path.parent / Path(*config_relative.parts),
        )
    healthcheck = internal_document.get("healthcheck")
    if isinstance(healthcheck, Mapping) and healthcheck.get("type") == "command":
        health_relative = _safe_relative_path(
            healthcheck.get("target"),
            "internal manifest healthcheck.target",
        )
        add_source(
            PurePosixPath(
                *internal_manifest_relative.parent.parts,
                *health_relative.parts,
            ).as_posix(),
            internal_manifest_path.parent / Path(*health_relative.parts),
        )

    release_manifest = json.loads(json.dumps(plugin_manifest))
    release_extension = release_manifest["meta"]["extension"]
    release_extension["source_adapter_entrypoint"] = release_extension[
        "adapter_entrypoint"
    ]
    release_extension["adapter_entrypoint"] = packaged_adapter_relative.as_posix()
    generated_files = {
        "plugin.json": json.dumps(
            release_manifest,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        + b"\n",
        "adapter/__init__.py": b'"""Packaged Channel Adapter namespace."""\n',
        str(packaged_adapter_relative.parent / "__init__.py"):
            b'"""Packaged provider Adapter."""\n',
        "core/__init__.py": b'"""Packaged Extension runtime core."""\n',
        "runtime/__init__.py": b'"""Packaged official Plugin runtime wrapper."""\n',
        "scripts/__init__.py": b'"""Packaged lifecycle support modules."""\n',
    }
    plugin_entry = plugin_root / "plugin.py"
    generated_files["plugin.py"] = _render_qwenpaw_plugin_entry(
        plugin_entry.read_text(encoding="utf-8"),
        package_namespace=package_namespace,
    ).encode("utf-8")

    # Keep the official compatibility layout at the archive root while loading
    # executable Python dependencies from a per-Plugin namespace. QwenPaw loads
    # multiple backend entries in one interpreter, so generic top-level package
    # names such as ``adapter`` and ``runtime`` cannot safely identify a Plugin.
    namespace_prefixes = (
        "adapter/",
        "contracts/",
        "core/",
        "runtime/",
        "schemas/",
        "scripts/",
    )
    generated_files[f"{package_namespace}/__init__.py"] = (
        f'"""Private runtime namespace for {plugin_manifest["id"]}."""\n'
    ).encode("utf-8")
    for target, source in sorted(sources.items()):
        plugin_local_python = (
            source.parent == plugin_root
            and source.suffix.lower() == ".py"
            and target not in {"plugin.py", "__init__.py"}
        )
        if not target.startswith(namespace_prefixes) and not plugin_local_python:
            continue
        namespaced_target = f"{package_namespace}/{target}"
        content = source.read_bytes()
        if source.suffix.lower() == ".py":
            content = _rewrite_namespaced_python(
                content.decode("utf-8"),
                package_namespace=package_namespace,
            ).encode("utf-8")
        generated_files[namespaced_target] = content
    for target, content in tuple(generated_files.items()):
        if not target.startswith(namespace_prefixes):
            continue
        namespaced_target = f"{package_namespace}/{target}"
        if namespaced_target in generated_files:
            continue
        generated_files[namespaced_target] = content
    collisions = sorted(set(generated_files).intersection(sources))
    if collisions:
        raise ExtensionPackagingError(
            f"generated Plugin paths collide with sources: {', '.join(collisions)}"
        )

    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{plugin_manifest['id']}-v{plugin_manifest['version']}.zip"
    temporary_archive = output / f".{archive.name}.{os.getpid()}.tmp"
    try:
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as package:
            for target, source in sorted(sources.items()):
                if target.startswith("scripts/") and source.suffix.lower() == ".py":
                    _write_bytes(
                        package,
                        target,
                        _remove_repository_path_injection(
                            source.read_text(encoding="utf-8")
                        ).encode("utf-8"),
                        executable=_is_executable_source(source),
                    )
                else:
                    _write_source_file(package, source, target)
            for target, content in sorted(generated_files.items()):
                _write_bytes(package, target, content)
        temporary_archive.replace(archive)
    finally:
        if temporary_archive.exists():
            temporary_archive.unlink()

    digest = sha256_file(archive)
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{digest}  {archive.name}\n",
        encoding="utf-8",
    )
    return PackageResult(
        name=str(plugin_manifest["id"]),
        type="channel",
        version=internal_metadata.version,
        archive=archive,
        sha256=digest,
        source_file_count=len(sources) + len(generated_files),
    )


def _qwenpaw_plugin_namespace(plugin_id: str) -> str:
    """Return a deterministic, import-safe namespace for one official Plugin."""

    normalized = re.sub(r"[^a-z0-9]+", "_", plugin_id.lower()).strip("_")
    if not normalized:
        raise ExtensionPackagingError("official Plugin id has no namespace value")
    return f"qwenpaw_plugin_{normalized}"


def _remove_repository_path_injection(source: str) -> str:
    """Remove repository-root ``sys.path`` mutations from release-only code."""

    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)if str\((?P<root>[A-Z_]+)\) not in sys\.path:\r?\n"
        r"(?P=indent)[ \t]+sys\.path\.insert\(0, str\((?P=root)\)\)\r?\n"
    )
    return pattern.sub("", source)


def _rewrite_namespaced_python(source: str, *, package_namespace: str) -> str:
    """Rewrite bundled internal imports into one Plugin-private namespace."""

    rewritten = _remove_repository_path_injection(source)
    for package_name in ("adapter", "contracts", "core", "runtime", "scripts"):
        rewritten = re.sub(
            rf"(?m)^(?P<indent>[ \t]*)from {package_name}(?=\.|\s+import)",
            rf"\g<indent>from {package_namespace}.{package_name}",
            rewritten,
        )
        rewritten = re.sub(
            rf"(?m)^(?P<indent>[ \t]*)import {package_name}(?=\.|\s|$)",
            rf"\g<indent>import {package_namespace}.{package_name}",
            rewritten,
        )
    return rewritten


def _render_qwenpaw_plugin_entry(
    source: str,
    *,
    package_namespace: str,
) -> str:
    """Render a self-contained backend entry without global import-path hacks."""

    rewritten = _rewrite_namespaced_python(
        source,
        package_namespace=package_namespace,
    )
    anchor = "SELF_CONTAINED = PACKAGED_ADAPTER_PATH.is_file() and PACKAGED_WRAPPER_PATH.is_file()\n"
    if anchor not in rewritten:
        raise ExtensionPackagingError(
            "official Plugin entry is missing the self-contained package anchor"
        )
    bootstrap = f'''\nPACKAGED_NAMESPACE = "{package_namespace}"


def _load_packaged_namespace() -> None:
    """Load this Plugin's private package without mutating ``sys.path``."""

    namespace_root = PLUGIN_ROOT / PACKAGED_NAMESPACE
    namespace_init = namespace_root / "__init__.py"
    existing = sys.modules.get(PACKAGED_NAMESPACE)
    if existing is not None:
        existing_file = Path(getattr(existing, "__file__", "")).resolve()
        if existing_file != namespace_init.resolve():
            raise RuntimeError(
                f"Plugin namespace collision: {{PACKAGED_NAMESPACE}}"
            )
        return
    spec = importlib.util.spec_from_file_location(
        PACKAGED_NAMESPACE,
        namespace_init,
        submodule_search_locations=[str(namespace_root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Plugin namespace: {{namespace_init}}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGED_NAMESPACE] = module
    spec.loader.exec_module(module)
'''
    rewritten = rewritten.replace(anchor, anchor + bootstrap, 1)
    branch_anchor = "if SELF_CONTAINED:\n    REPOSITORY_ROOT = PLUGIN_ROOT\n"
    if branch_anchor not in rewritten:
        raise ExtensionPackagingError(
            "official Plugin entry is missing the packaged execution branch"
        )
    rewritten = rewritten.replace(
        branch_anchor,
        branch_anchor + "    _load_packaged_namespace()\n",
        1,
    )
    return rewritten


def build_qwenpaw_plugins(
    repository_root: str | Path,
    output_directory: str | Path,
    *,
    names: Sequence[str] | None = None,
) -> tuple[PackageResult, ...]:
    """Build selected official Channel Plugin facades in stable order."""

    repository = Path(repository_root).resolve()
    plugin_root = repository / "plugins"
    available = {
        path.name: path
        for path in plugin_root.glob("*-channel-plugin")
        if path.is_dir() and (path / "plugin.json").is_file()
    }
    selected = set(names or available)
    unknown = sorted(selected - set(available))
    if unknown:
        raise ExtensionPackagingError(
            f"unknown official Channel Plugins: {', '.join(unknown)}"
        )
    results = tuple(
        build_qwenpaw_plugin(
            available[name],
            output_directory,
            repository_root=repository,
        )
        for name in sorted(selected)
    )
    _write_checksum_index(Path(output_directory).resolve(), results)
    return results


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
        if is_excluded_package_path(relative):
            continue
        if candidate.is_file():
            files.append(candidate)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def is_excluded_package_path(relative: Path) -> bool:
    """Return whether a relative path is forbidden in a release package."""

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


def _validate_qwenpaw_plugin_manifest(
    manifest: Mapping[str, Any],
    *,
    plugin_root: Path,
    repository_root: Path,
) -> dict[str, Any]:
    required_fields = {
        "id",
        "name",
        "version",
        "type",
        "description",
        "entry",
        "meta",
    }
    missing = sorted(required_fields - set(manifest))
    if missing:
        raise ExtensionPackagingError(
            f"official Plugin manifest is missing: {', '.join(missing)}"
        )
    plugin_id = manifest["id"]
    if (
        not isinstance(plugin_id, str)
        or QWENPAW_PLUGIN_ID_PATTERN.fullmatch(plugin_id) is None
    ):
        raise ExtensionPackagingError("official Plugin id must use lowercase kebab-case")
    version = manifest["version"]
    if (
        not isinstance(version, str)
        or QWENPAW_PLUGIN_VERSION_PATTERN.fullmatch(version) is None
    ):
        raise ExtensionPackagingError("official Plugin version must use SemVer")
    if manifest["type"] != "channel":
        raise ExtensionPackagingError("official Channel Plugin type must be channel")

    entry = manifest["entry"]
    if not isinstance(entry, Mapping) or set(entry) != {"backend"}:
        raise ExtensionPackagingError(
            "official Plugin entry must contain only backend"
        )
    entry_relative = _safe_relative_path(entry["backend"], "entry.backend")
    entry_path = (plugin_root / Path(*entry_relative.parts)).resolve()
    if not entry_path.is_relative_to(plugin_root) or not entry_path.is_file():
        raise ExtensionPackagingError(
            f"official Plugin backend entry does not exist: {entry_path}"
        )

    meta = manifest["meta"]
    if not isinstance(meta, Mapping):
        raise ExtensionPackagingError("official Plugin meta must be a mapping")
    extension = meta.get("extension")
    if not isinstance(extension, Mapping):
        raise ExtensionPackagingError("meta.extension must be a mapping")
    manifest_relative = _safe_relative_path(
        extension.get("manifest"),
        "meta.extension.manifest",
    )
    adapter_relative = _safe_relative_path(
        extension.get("adapter_entrypoint"),
        "meta.extension.adapter_entrypoint",
    )
    if not adapter_relative.parts or adapter_relative.parts[0] != "adapters":
        raise ExtensionPackagingError(
            "meta.extension.adapter_entrypoint must reference adapters/"
        )
    internal_manifest_path = (
        repository_root / Path(*manifest_relative.parts)
    ).resolve()
    adapter_source_path = (
        repository_root / Path(*adapter_relative.parts)
    ).resolve()
    if not internal_manifest_path.is_relative_to(repository_root):
        raise ExtensionPackagingError("internal Manifest escapes repository root")
    if not adapter_source_path.is_relative_to(repository_root):
        raise ExtensionPackagingError("Adapter entrypoint escapes repository root")
    if not adapter_source_path.is_file():
        raise ExtensionPackagingError(
            f"Adapter entrypoint does not exist: {adapter_source_path}"
        )

    loader = ExtensionLoader(repository_root / "schemas" / "extension-manifest.schema.json")
    internal_metadata = loader.load_metadata(internal_manifest_path)
    expected_values = {
        "name": internal_metadata.name,
        "type": internal_metadata.type.value,
        "runtime": internal_metadata.runtime.value,
        "declared_entrypoint": internal_metadata.entrypoint,
    }
    for field, expected in expected_values.items():
        if extension.get(field) != expected:
            raise ExtensionPackagingError(
                f"meta.extension.{field} does not match internal Manifest"
            )
    if version != internal_metadata.version:
        raise ExtensionPackagingError(
            "official Plugin version does not match internal Extension version"
        )

    permissions = meta.get("permissions")
    if (
        not isinstance(permissions, list)
        or not permissions
        or any(not isinstance(item, str) or not item.strip() for item in permissions)
        or len(permissions) != len(set(permissions))
    ):
        raise ExtensionPackagingError(
            "meta.permissions must be a non-empty unique string list"
        )
    config = meta.get("config")
    if not isinstance(config, Mapping):
        raise ExtensionPackagingError("meta.config must be a mapping")
    values = config.get("values")
    if not isinstance(values, Mapping) or values:
        raise ExtensionPackagingError(
            "official Plugin release must not contain configuration values"
        )
    fields = config.get("fields")
    if not isinstance(fields, list) or any(
        not isinstance(item, Mapping) for item in fields
    ):
        raise ExtensionPackagingError(
            "meta.config.fields must be a list of mappings"
        )
    field_names = [item.get("name") for item in fields]
    if any(not isinstance(name, str) or not name for name in field_names):
        raise ExtensionPackagingError(
            "Plugin config field names must be non-empty text"
        )
    if len(field_names) != len(set(field_names)):
        raise ExtensionPackagingError("Plugin config field names must be unique")
    secret_field_names = [
        item["name"] for item in fields if item.get("secret") is True
    ]
    official_secrets = list(meta.get("required_secrets", []))
    if official_secrets != secret_field_names:
        raise ExtensionPackagingError(
            "required_secrets must match password/secret Plugin config fields"
        )

    internal_secrets = list(
        _read_json_object(internal_manifest_path).get("required_secrets", [])
    )
    config_mapping = extension.get("config_mapping")
    if config_mapping is None:
        if official_secrets != internal_secrets:
            raise ExtensionPackagingError(
                "required secret names do not match internal Manifest"
            )
    else:
        if not isinstance(config_mapping, Mapping):
            raise ExtensionPackagingError(
                "meta.extension.config_mapping must be a mapping"
            )
        if set(config_mapping) - set(field_names):
            raise ExtensionPackagingError(
                "config_mapping contains an undeclared Plugin config field"
            )
        targets = list(config_mapping.values())
        if any(not isinstance(target, str) or not target for target in targets):
            raise ExtensionPackagingError(
                "config_mapping targets must be non-empty strings"
            )
        if len(targets) != len(set(targets)):
            raise ExtensionPackagingError("config_mapping targets must be unique")
        if set(targets) != set(internal_secrets):
            raise ExtensionPackagingError(
                "config_mapping must cover the internal Manifest requirements"
            )
        if not set(official_secrets).issubset(config_mapping):
            raise ExtensionPackagingError(
                "every Plugin secret field must have an internal config mapping"
            )
    return {
        "internal_manifest_path": internal_manifest_path,
        "adapter_source_path": adapter_source_path,
        "internal_metadata": internal_metadata,
    }


def _safe_relative_path(value: Any, field_name: str) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise ExtensionPackagingError(f"{field_name} must be non-empty text")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or re.match(r"^[A-Za-z]:", value)
        or "\\" in value
    ):
        raise ExtensionPackagingError(f"{field_name} must be a safe POSIX path")
    return relative


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
    parser.add_argument(
        "--qwenpaw-plugin",
        action="append",
        dest="qwenpaw_plugins",
        help=(
            "Build one self-contained official Channel Plugin directory name; "
            "repeat to select multiple."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.qwenpaw_plugins:
        if args.extensions:
            raise ExtensionPackagingError(
                "--extension and --qwenpaw-plugin cannot be combined"
            )
        results = build_qwenpaw_plugins(
            args.repository_root,
            Path(args.output) / "qwenpaw-plugins",
            names=args.qwenpaw_plugins,
        )
    else:
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
