"""Deterministic dependency and optional Runtime capability discovery."""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any, Iterable


CAPABILITY_SPECS: dict[str, dict[str, tuple[str, ...]]] = {
    "pillow": {"modules": ("PIL",)},
    "opencv": {"modules": ("cv2",)},
    "imagemagick": {"commands": ("magick", "convert")},
    "ffmpeg": {"commands": ("ffmpeg",)},
    "tesseract": {"commands": ("tesseract",), "modules": ("pytesseract",)},
    "paddleocr": {"modules": ("paddleocr",)},
    "openpyxl": {"modules": ("openpyxl",)},
    "pyarrow": {"modules": ("pyarrow",)},
    "yaml": {"modules": ("yaml",)},
    "7z": {"commands": ("7z", "7zz")},
    "asr": {"modules_any": ("whisper", "faster_whisper", "funasr")},
    "realesrgan": {"modules_any": ("realesrgan", "basicsr")},
    "gfpgan": {"modules": ("gfpgan",)},
    "codeformer": {"modules": ("codeformer",)},
    "lama": {"modules_any": ("lama_cleaner", "simple_lama_inpainting")},
    "colorization": {"modules_any": ("deoldify", "colorizers")},
    "background_removal": {"modules": ("rembg",)},
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


class CapabilityResolver:
    def resolve(self, name: str) -> dict[str, Any]:
        spec = CAPABILITY_SPECS.get(name)
        if spec is None:
            return {"name": name, "available": False, "mode": "unsupported"}
        modules = spec.get("modules", ())
        modules_any = spec.get("modules_any", ())
        commands = spec.get("commands", ())
        module_ok = all(importlib.util.find_spec(item) is not None for item in modules)
        any_ok = not modules_any or any(
            importlib.util.find_spec(item) is not None for item in modules_any
        )
        command_ok = not commands or any(shutil.which(item) for item in commands)
        available = module_ok and any_ok and command_ok
        return {
            "name": name,
            "available": bool(available),
            "mode": (
                "runtime"
                if available and name in MODEL_CAPABILITIES
                else "native"
                if available
                else "runtime_required"
                if name in MODEL_CAPABILITIES
                else "dependency_missing"
            ),
        }

    def resolve_many(self, names: Iterable[str]) -> dict[str, dict[str, Any]]:
        return {name: self.resolve(name) for name in names}
