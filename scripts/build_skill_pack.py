"""Build deterministic, isolated QwenPaw packages for the productivity Skills."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

try:
    from scripts.build_extension import build_extension
    from scripts.generate_core_skill_scaffolds import SKILLS
except ModuleNotFoundError:  # Direct ``python scripts/build_skill_pack.py``.
    from build_extension import build_extension
    from generate_core_skill_scaffolds import SKILLS


HANDLER_MODULES = {
    "image-toolkit": "image_tools",
    "photo-restoration": "image_tools",
    "image-background-tools": "image_tools",
    "image-quality-enhancer": "image_tools",
    "advanced-ocr": "ocr_media",
    "media-transcriber": "ocr_media",
    "sql-diagnostics": "diagnostics",
    "log-incident-analyzer": "diagnostics",
    "api-debugger": "diagnostics",
    "ops-troubleshooter": "diagnostics",
    "network-diagnostics": "diagnostics",
    "config-diagnostics": "diagnostics",
    "archive-inspector": "data_files",
    "data-profiler": "data_files",
    "document-batch-processor": "data_files",
    "release-notes": "research_release",
    "web-research-report": "research_release",
}

FORBIDDEN_SUFFIXES = {".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".pyc"}
FORBIDDEN_PARTS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", "cache", "logs"}
LOCAL_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|pyprograms|workspace)|/(?:root|home|workspace|app)/)")


@dataclass(frozen=True)
class SkillPackage:
    name: str
    version: str
    archive: str
    sha256: str
    entries: int


def _descriptor(skill_root: Path) -> dict:
    value = json.loads((skill_root / "skill.yaml").read_text(encoding="utf-8"))
    if value.get("name") != skill_root.name or value.get("version") != "1.0.0":
        raise ValueError(f"invalid Skill descriptor: {skill_root}")
    return value


def _source_files(skill_root: Path):
    for path in sorted(skill_root.rglob("*")):
        if not path.is_file(): continue
        relative = path.relative_to(skill_root)
        if "tests" in relative.parts or any(part.lower() in FORBIDDEN_PARTS for part in relative.parts): continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES: continue
        yield relative.as_posix(), path


def _validate_entry(name: str, content: bytes) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe ZIP entry: {name}")
    if any(part.lower() in FORBIDDEN_PARTS for part in path.parts):
        raise ValueError(f"forbidden cache/log entry: {name}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        raise ValueError(f"model/cache binary is forbidden: {name}")
    if path.suffix.lower() in {".py", ".md", ".json", ".yaml", ".txt"}:
        text = content.decode("utf-8")
        if LOCAL_ABSOLUTE.search(text):
            raise ValueError(f"local absolute path detected in {name}")


def _write(zip_file: zipfile.ZipFile, name: str, content: bytes) -> None:
    _validate_entry(name, content)
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zip_file.writestr(info, content)


def build_skill(repository_root: Path, output_root: Path, name: str) -> SkillPackage:
    if name not in SKILLS: raise KeyError(name)
    skill_root = repository_root / "skills" / name
    descriptor = _descriptor(skill_root)
    output_root.mkdir(parents=True, exist_ok=True)
    archive = output_root / f"{name}.skill.zip"
    handler = HANDLER_MODULES[name]
    runtime_root = repository_root / "core" / "productivity_skills"
    entries = 0
    with zipfile.ZipFile(archive, "w") as package:
        for target, source in _source_files(skill_root):
            _write(package, target, source.read_bytes()); entries += 1
        runtime_files = {
            "runtime/__init__.py": runtime_root / "__init__.py",
            "runtime/executor.py": runtime_root / "executor.py",
            "runtime/models.py": runtime_root / "models.py",
            "runtime/artifacts.py": runtime_root / "artifacts.py",
            "runtime/capabilities.py": runtime_root / "capabilities.py",
            "runtime/runtimes.py": runtime_root / "runtimes.py",
            "runtime/handlers/__init__.py": runtime_root / "handlers" / "__init__.py",
            f"runtime/handlers/{handler}.py": runtime_root / "handlers" / f"{handler}.py",
        }
        for source in sorted((runtime_root / "runtime").rglob("*.py")):
            relative = source.relative_to(runtime_root / "runtime").as_posix()
            runtime_files[f"runtime/runtime/{relative}"] = source
        for target, source in runtime_files.items():
            _write(package, target, source.read_bytes()); entries += 1
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        required = {"SKILL.md", "skill.yaml", "scripts/run.py", "runtime/__init__.py"}
        if not required.issubset(names) or package.testzip() is not None:
            raise ValueError(f"invalid Skill archive: {archive}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return SkillPackage(name, descriptor["version"], str(archive), digest, entries)


def build_advanced_pdf(repository_root: Path, output_root: Path) -> SkillPackage:
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        built = build_extension(repository_root / "skills" / "pdf-editor" / "manifest.yaml", Path(temporary))
        archive = output_root / "advanced-pdf-editor.skill.zip"
        shutil.copyfile(built.archive, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as package: entries = len(package.namelist())
    return SkillPackage("advanced-pdf-editor", "1.2.0", str(archive), digest, entries)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", default="dist/skills")
    parser.add_argument("--skill", action="append", choices=sorted(SKILLS))
    parser.add_argument("--without-advanced-pdf", action="store_true")
    args = parser.parse_args()
    repository_root = Path(args.repository_root).resolve()
    output = Path(args.output)
    if not output.is_absolute(): output = repository_root / output
    names = args.skill or list(SKILLS)
    results = [build_skill(repository_root, output, name) for name in names]
    if not args.without_advanced_pdf and not args.skill:
        results.append(build_advanced_pdf(repository_root, output))
    print(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
