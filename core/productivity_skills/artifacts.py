"""Safe output and Artifact helpers."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Mapping


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_output_path(
    request: Mapping[str, Any],
    *,
    source: Path | None,
    stem_suffix: str,
    extension: str,
) -> Path:
    output_dir_value = request.get("output_dir")
    output_dir = (
        Path(str(output_dir_value)).expanduser()
        if output_dir_value
        else ((source.parent if source else Path.cwd()) / "artifacts")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    base = source.stem if source else "report"
    suffix = extension if extension.startswith(".") else f".{extension}"
    candidate = output_dir / f"{base}_{stem_suffix}{suffix}"
    counter = 1
    while candidate.exists() or (source is not None and candidate.resolve() == source.resolve()):
        candidate = output_dir / f"{base}_{stem_suffix}_{counter}{suffix}"
        counter += 1
    return candidate


def artifact(
    path: Path,
    *,
    operation: str,
    source: Path | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(path)
    mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    metadata: dict[str, Any] = {
        "operation": operation,
        "source": source.name if source else None,
        "output": resolved.name,
        "mime_type": mime_type,
        "size": resolved.stat().st_size,
        "checksum": sha256_file(resolved),
    }
    if extra:
        metadata.update(extra)
    return {
        "artifact_id": f"sha256:{metadata['checksum']}",
        "uri": f"artifact://{resolved.name}",
        "filename": resolved.name,
        "mime_type": mime_type,
        "metadata": metadata,
    }


def write_report(
    request: Mapping[str, Any],
    content: str,
    *,
    operation: str,
    suffix: str = "report",
    extension: str = ".md",
    source: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    output = safe_output_path(
        request,
        source=source,
        stem_suffix=suffix,
        extension=extension,
    )
    output.write_text(content, encoding="utf-8")
    return output, artifact(output, operation=operation, source=source)
