"""Build the self-contained QwenPaw SenseNova image-generation Tool Plugin."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile


PLUGIN_ID = "sensenova-image-generation-tool"
PLUGIN_VERSION = "1.0.2"
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def _sources(repository_root: Path) -> list[tuple[Path, str]]:
    plugin_root = repository_root / "plugins" / PLUGIN_ID
    files: list[tuple[Path, str]] = [
        (plugin_root / name, name)
        for name in ("plugin.json", "plugin.py", "sensenova_image_generation.py", "README.md")
    ]
    for source in sorted((repository_root / "core" / "image_generation").rglob("*.py")):
        relative = source.relative_to(repository_root).as_posix()
        files.append((source, relative))
    for source in sorted((repository_root / "core" / "contracts").glob("*.py")):
        relative = source.relative_to(repository_root).as_posix()
        files.append((source, relative))
    for source in sorted(
        (repository_root / "core" / "productivity_skills").rglob("*.py")
    ):
        relative = source.relative_to(repository_root).as_posix()
        files.append((source, relative))
    missing = [str(source) for source, _ in files if not source.is_file()]
    if missing:
        raise FileNotFoundError("missing Plugin source: " + ", ".join(missing))
    return files


def build(repository_root: Path, output_root: Path) -> tuple[Path, str]:
    repository_root = repository_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    archive = output_root / f"{PLUGIN_ID}-v{PLUGIN_VERSION}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for source, archive_name in sorted(_sources(repository_root), key=lambda item: item[1]):
            info = zipfile.ZipInfo(archive_name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, source.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8"
    )
    return archive, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        default=Path("dist") / "extensions" / "qwenpaw-plugins",
    )
    args = parser.parse_args()
    archive, digest = build(Path(args.repository_root), Path(args.output))
    print(f"{archive}\nSHA256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
