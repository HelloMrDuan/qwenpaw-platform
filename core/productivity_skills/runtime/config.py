"""Workspace-relative model cache and environment configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "on"}


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    asr_models: Path
    rembg_models: Path

    @classmethod
    def from_env(cls) -> "RuntimePaths":
        workspace_value = os.environ.get("QWENPAW_WORKSPACE")
        workspace = Path(workspace_value).expanduser() if workspace_value else Path.cwd()
        root = _path_from_env("QWENPAW_RUNTIME_ROOT", workspace / ".runtime")
        return cls(
            root=root,
            asr_models=_path_from_env("QWENPAW_ASR_CACHE_DIR", root / "models" / "asr"),
            rembg_models=_path_from_env("QWENPAW_REMBG_MODEL_DIR", root / "models" / "rembg"),
        )


def model_download_allowed() -> bool:
    return os.environ.get("QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD", "").lower() in TRUE_VALUES
