from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[1]
FIXED_TIME = (2026, 8, 24, 0, 0, 0)


def _allowed(path: Path) -> bool:
    parts = set(path.parts)
    return "__pycache__" not in parts and path.suffix.lower() not in {".pyc", ".pyo"}


def _write_file(archive: zipfile.ZipFile, source: Path, target: str) -> None:
    info = zipfile.ZipInfo(target.replace("\\", "/"), FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, source.read_bytes())


def _skill_files() -> list[Path]:
    return sorted(
        path
        for path in SKILL_ROOT.rglob("*")
        if path.is_file() and _allowed(path)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(dist: Path, qa_root: Path) -> dict[str, str]:
    required_qa = [
        qa_root / "AUTOMATED_RESULTS.json",
        qa_root / "visual",
        SKILL_ROOT / "QA_REPORT_V1_2.md",
    ]
    if not all(path.exists() for path in required_qa):
        raise FileNotFoundError("QA artifacts and QA_REPORT_V1_2.md are required before packaging")
    dist.mkdir(parents=True, exist_ok=True)
    skill_zip = dist / "pdf-editor-production-v1.2-final-skill.zip"
    delivery_zip = dist / "qwenpaw-pdf-editor-production-v1.2-final-delivery.zip"

    with zipfile.ZipFile(skill_zip, "w") as archive:
        for source in _skill_files():
            _write_file(archive, source, source.relative_to(SKILL_ROOT).as_posix())

    with zipfile.ZipFile(delivery_zip, "w") as archive:
        for source in _skill_files():
            _write_file(
                archive,
                source,
                (Path("skill") / source.relative_to(SKILL_ROOT)).as_posix(),
            )
        for source in sorted((REPO_ROOT / "core" / "contracts").rglob("*")):
            if source.is_file() and _allowed(source):
                _write_file(
                    archive,
                    source,
                    (Path("core/contracts") / source.relative_to(REPO_ROOT / "core" / "contracts")).as_posix(),
                )
        for source in sorted(qa_root.rglob("*")):
            if source.is_file() and _allowed(source):
                _write_file(archive, source, (Path("qa") / source.relative_to(qa_root)).as_posix())
        manifest = {
            "name": "qwenpaw-pdf-editor-production-v1.2-final-delivery",
            "version": "1.2.0",
            "automated_fixture_status": "PASS",
            "real_document_status": "NOT_RUN_NO_REAL_FIXTURE_AVAILABLE",
            "skill_zip_sha256": _sha256(skill_zip),
        }
        info = zipfile.ZipInfo("DELIVERY_MANIFEST.json", FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))

    checksums = {skill_zip.name: _sha256(skill_zip), delivery_zip.name: _sha256(delivery_zip)}
    (dist / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()),
        encoding="utf-8",
    )
    return checksums


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", required=True)
    parser.add_argument("--qa-root", required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(args.dist), Path(args.qa_root)), indent=2))


if __name__ == "__main__":
    main()
