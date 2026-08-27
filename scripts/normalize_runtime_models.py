"""Inspect or symlink discovered model caches into the workspace Runtime tree."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.productivity_skills.runtime import FasterWhisperConfig, RembgConfig
from core.productivity_skills.runtime.config import RuntimePaths
from core.productivity_skills.runtime.errors import RuntimeUnavailableError


@dataclass(frozen=True)
class ModelLocation:
    runtime: str
    model: str
    source: str | None
    target: str
    size: int
    needs_migration: bool
    status: str
    error: str | None = None


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def inspect_models() -> list[ModelLocation]:
    paths = RuntimePaths.from_env()
    results = []
    try:
        asr = FasterWhisperConfig.from_env()
        asr_source = asr.discover_model()
        asr_error = None
    except RuntimeUnavailableError as exc:
        asr = None
        asr_source = None
        asr_error = str(exc)
    asr_model = asr.model if asr else os.environ.get("QWENPAW_ASR_MODEL", "tiny")
    asr_target = paths.asr_models / asr_model
    results.append(
        ModelLocation(
            runtime="asr",
            model=asr_model,
            source=str(asr_source) if asr_source else None,
            target=str(asr_target),
            size=_tree_size(asr_source) if asr_source else 0,
            needs_migration=bool(asr_source and asr_source.resolve() != asr_target.resolve()),
            status="FOUND" if asr_source else "MISSING",
            error=asr_error,
        )
    )
    try:
        rembg = RembgConfig.from_env()
        rembg_file = rembg.discover_model_file()
        rembg_error = None
    except RuntimeUnavailableError as exc:
        rembg = None
        rembg_file = None
        rembg_error = str(exc)
    rembg_model = rembg.model if rembg else os.environ.get("QWENPAW_REMBG_MODEL", "u2netp")
    rembg_source = rembg_file.parent if rembg_file else None
    rembg_target = paths.rembg_models / rembg_model
    results.append(
        ModelLocation(
            runtime="background_removal",
            model=rembg_model,
            source=str(rembg_source) if rembg_source else None,
            target=str(rembg_target),
            size=_tree_size(rembg_source) if rembg_source else 0,
            needs_migration=bool(rembg_source and rembg_source.resolve() != rembg_target.resolve()),
            status="FOUND" if rembg_source else "MISSING",
            error=rembg_error,
        )
    )
    return results


def link_models(locations: list[ModelLocation]) -> list[ModelLocation]:
    output = []
    for item in locations:
        if not item.source:
            output.append(item)
            continue
        source = Path(item.source)
        target = Path(item.target)
        if not item.needs_migration:
            output.append(ModelLocation(**{**asdict(item), "status": "ALREADY_NORMALIZED"}))
            continue
        if os.path.lexists(target):
            output.append(
                ModelLocation(
                    **{
                        **asdict(item),
                        "status": "TARGET_EXISTS",
                        "error": "target exists; no file was replaced",
                    }
                )
            )
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            output.append(
                ModelLocation(
                    **{
                        **asdict(item),
                        "status": "LINK_UNSUPPORTED",
                        "error": str(exc),
                    }
                )
            )
            continue
        output.append(
            ModelLocation(
                **{
                    **asdict(item),
                    "needs_migration": False,
                    "status": "LINKED",
                }
            )
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect", action="store_true", help="report only; never modify files")
    action.add_argument("--link", action="store_true", help="create directory symlinks; never copy models")
    args = parser.parse_args()
    locations = inspect_models()
    if args.link:
        locations = link_models(locations)
    print(json.dumps([asdict(item) for item in locations], ensure_ascii=False, indent=2))
    unsafe = {"LINK_UNSUPPORTED", "TARGET_EXISTS"}
    return 2 if any(item.status in unsafe for item in locations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
