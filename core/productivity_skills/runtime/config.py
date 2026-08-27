"""Workspace-relative model cache and environment configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable


TRUE_VALUES = {"1", "true", "yes", "on"}


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    asr_models: Path
    rembg_models: Path
    configured_asr_cache: Path | None = None
    configured_rembg_models: Path | None = None
    huggingface_caches: tuple[Path, ...] = ()
    rembg_caches: tuple[Path, ...] = ()

    @classmethod
    def from_env(cls) -> "RuntimePaths":
        workspace_value = os.environ.get("QWENPAW_WORKSPACE")
        workspace = Path(workspace_value).expanduser() if workspace_value else Path.cwd()
        root = _path_from_env("QWENPAW_RUNTIME_ROOT", workspace / ".runtime")
        configured_asr = os.environ.get("QWENPAW_ASR_CACHE_DIR")
        configured_rembg = os.environ.get("QWENPAW_REMBG_MODEL_DIR")
        try:
            home = Path.home()
        except RuntimeError:
            home = workspace
        hf_home = Path(os.environ.get("HF_HOME", home / ".cache" / "huggingface")).expanduser()
        xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache")).expanduser()
        huggingface_caches = _unique_paths(
            path
            for path in (
                os.environ.get("HF_HUB_CACHE"),
                os.environ.get("HUGGINGFACE_HUB_CACHE"),
                hf_home / "hub",
                xdg_cache / "huggingface" / "hub",
                home / ".cache" / "huggingface" / "hub",
            )
            if path
        )
        return cls(
            root=root,
            asr_models=root / "models" / "asr",
            rembg_models=root / "models" / "rembg",
            configured_asr_cache=Path(configured_asr).expanduser() if configured_asr else None,
            configured_rembg_models=Path(configured_rembg).expanduser() if configured_rembg else None,
            huggingface_caches=huggingface_caches,
            rembg_caches=_unique_paths(
                path
                for path in (
                    Path(configured_rembg).expanduser() if configured_rembg else None,
                    home / ".rembg" / "models",
                )
                if path is not None
            ),
        )


def model_download_allowed() -> bool:
    return os.environ.get("QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD", "").lower() in TRUE_VALUES


def _unique_paths(values: Iterable[Path | str]) -> tuple[Path, ...]:
    result = []
    seen = set()
    for value in values:
        path = Path(value).expanduser()
        key = str(path.absolute()).casefold()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return tuple(result)
