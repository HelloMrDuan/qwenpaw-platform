"""Dependency and Runtime discovery with structured health states."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import subprocess
from typing import Any, Iterable


CAPABILITY_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "pillow": {"modules": ("PIL",), "packages": ("Pillow",)},
    "opencv": {"modules": ("cv2",), "packages": ("opencv-python-headless", "opencv-python")},
    "imagemagick": {"commands_any": ("magick", "convert")},
    "ffmpeg": {"commands": ("ffmpeg", "ffprobe")},
    "tesseract": {"commands": ("tesseract",), "modules": ("pytesseract",), "packages": ("pytesseract",)},
    "paddleocr": {"modules": ("paddleocr",), "packages": ("paddleocr",)},
    "openpyxl": {"modules": ("openpyxl",), "packages": ("openpyxl",)},
    "pyarrow": {"modules": ("pyarrow",), "packages": ("pyarrow",)},
    "yaml": {"modules": ("yaml",), "packages": ("PyYAML",)},
    "7z": {"commands_any": ("7z", "7zz")},
    "asr": {"modules": ("faster_whisper",), "packages": ("faster-whisper",)},
    "realesrgan": {"modules_any": ("realesrgan", "basicsr")},
    "gfpgan": {"modules": ("gfpgan",), "packages": ("gfpgan",)},
    "codeformer": {"modules": ("codeformer",)},
    "lama": {"modules_any": ("lama_cleaner", "simple_lama_inpainting")},
    "colorization": {"modules_any": ("deoldify", "colorizers")},
    "background_removal": {"modules": ("rembg",), "packages": ("rembg",)},
}

MODEL_CAPABILITIES = {
    "asr",
    "realesrgan",
    "gfpgan",
    "codeformer",
    "lama",
    "colorization",
    "background_removal",
}


def _package_version(names: tuple[str, ...]) -> tuple[str | None, str | None]:
    for name in names:
        try:
            return name, importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None, None


def _binary_version(binary: str | None) -> str | None:
    if not binary:
        return None
    try:
        flag = "-version" if any(name in binary.lower() for name in ("ffmpeg", "ffprobe")) else "--version"
        completed = subprocess.run(
            [binary, flag],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        first = (completed.stdout or completed.stderr).splitlines()
        return first[0].strip() if first else None
    except (OSError, subprocess.SubprocessError):
        return None


class CapabilityResolver:
    def _runtime_health(self, name: str, *, runtime_test: bool) -> dict[str, Any]:
        try:
            if name == "asr":
                from .runtime import FasterWhisperAdapter

                return FasterWhisperAdapter.from_request().healthcheck(load_model=runtime_test)
            if name == "background_removal":
                from .runtime import RembgAdapter

                return RembgAdapter.from_request().healthcheck(runtime_test=runtime_test)
        except Exception as exc:
            return {"status": "RUNTIME_ERROR", "runtime_test": "failed", "error": str(exc)}
        return {"status": "AVAILABLE", "runtime_test": "not_applicable", "error": None}

    def resolve(self, name: str, *, runtime_test: bool = False) -> dict[str, Any]:
        spec = CAPABILITY_SPECS.get(name)
        if spec is None:
            return {
                "name": name,
                "available": False,
                "status": "MISSING",
                "mode": "unsupported",
                "runtime_test": "unsupported",
                "error": "unknown capability",
            }
        modules = spec.get("modules", ())
        modules_any = spec.get("modules_any", ())
        commands = spec.get("commands", ())
        commands_any = spec.get("commands_any", ())
        missing_modules = [item for item in modules if importlib.util.find_spec(item) is None]
        any_module_ok = not modules_any or any(importlib.util.find_spec(item) is not None for item in modules_any)
        binary_paths = [shutil.which(item) for item in commands]
        any_binary_paths = [shutil.which(item) for item in commands_any]
        commands_ok = all(binary_paths)
        commands_any_ok = not commands_any or any(any_binary_paths)
        base_available = not missing_modules and any_module_ok and commands_ok and commands_any_ok
        binary = next((path for path in binary_paths + any_binary_paths if path), None)
        package_name, version = _package_version(spec.get("packages", ()))
        runtime_health = {"status": "AVAILABLE", "runtime_test": "not_required", "error": None}
        if base_available and name in {"asr", "background_removal"}:
            runtime_health = self._runtime_health(name, runtime_test=runtime_test)
        status = runtime_health["status"] if base_available else "MISSING"
        available = status == "AVAILABLE"
        missing = list(missing_modules)
        if modules_any and not any_module_ok:
            missing.append("one of: " + ", ".join(modules_any))
        missing.extend(command for command, path in zip(commands, binary_paths) if not path)
        if commands_any and not commands_any_ok:
            missing.append("one of: " + ", ".join(commands_any))
        error = runtime_health.get("error") or ("missing " + ", ".join(missing) if missing else None)
        return {
            "name": name,
            "available": available,
            "status": status,
            "mode": (
                "runtime"
                if available and name in MODEL_CAPABILITIES
                else "native"
                if available
                else "runtime_required"
                if name in MODEL_CAPABILITIES
                else "dependency_missing"
            ),
            "version": version or _binary_version(binary),
            "binary": binary,
            "python_package": package_name,
            "runtime_test": runtime_health.get("runtime_test", "not_run"),
            "error": error,
        }

    def resolve_many(
        self,
        names: Iterable[str],
        *,
        runtime_test: bool = False,
    ) -> dict[str, dict[str, Any]]:
        if runtime_test:
            return {name: self.resolve(name, runtime_test=True) for name in names}
        return {name: self.resolve(name) for name in names}
