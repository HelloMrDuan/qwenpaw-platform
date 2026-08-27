"""Official QwenPaw Tool Plugin entry for SenseNova image generation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


PLUGIN_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = PLUGIN_ROOT if (PLUGIN_ROOT / "core" / "image_generation").is_dir() else PLUGIN_ROOT.parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _load_tool_module():
    path = PLUGIN_ROOT / "sensenova_image_generation.py"
    spec = importlib.util.spec_from_file_location(
        "qwenpaw_sensenova_image_generation_tool", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load SenseNova Tool module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SenseNovaImageGenerationToolPlugin:
    def register(self, api) -> None:
        tool = _load_tool_module()
        api.register_tool(
            tool_name="image_generation",
            tool_func=tool.image_generation,
            description=tool.TOOL_DESCRIPTION,
            icon="🎨",
            enabled=False,
            tool_type="network",
        )
        api.register_middleware(
            tool.image_generation_middleware_factory,
            priority=40,
        )


plugin = SenseNovaImageGenerationToolPlugin()
