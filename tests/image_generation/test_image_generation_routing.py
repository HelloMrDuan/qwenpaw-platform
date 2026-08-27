from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from core.image_generation.routing import route_image_request
from scripts.build_image_generation_plugin import build


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakePluginApi:
    def __init__(self) -> None:
        self.calls = []
        self.middleware_calls = []

    def register_tool(self, **kwargs) -> None:
        self.calls.append(kwargs)

    def register_middleware(self, factory, *, priority=100) -> None:
        self.middleware_calls.append((factory, priority))


class ImageGenerationRoutingTests(unittest.TestCase):
    def test_required_routes_are_strictly_separated(self) -> None:
        cases = {
            "生成一张赛博朋克城市": "image_generation",
            "把这张图片压缩": "image-toolkit",
            "修复这张老照片": "photo-restoration",
            "把背景去掉": "image-background-tools",
            "把这张图放大2倍": "image-quality-enhancer",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(route_image_request(prompt), expected)

    def test_existing_input_blocks_text_to_image_route(self) -> None:
        self.assertNotEqual(
            route_image_request("根据描述生成图片", has_input_image=True),
            "image_generation",
        )

    def test_official_plugin_registers_disabled_tool_with_narrow_description(self) -> None:
        path = REPOSITORY_ROOT / "plugins" / "sensenova-image-generation-tool" / "plugin.py"
        spec = importlib.util.spec_from_file_location("sensenova_plugin_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        api = FakePluginApi()
        module.plugin.register(api)
        self.assertEqual(len(api.calls), 1)
        call = api.calls[0]
        self.assertEqual(call["tool_name"], "image_generation")
        self.assertFalse(call["enabled"])
        self.assertIn("brand-new image", call["description"])
        self.assertIn("existing image", call["description"])
        self.assertEqual(call["tool_type"], "network")
        self.assertEqual(len(api.middleware_calls), 1)
        self.assertEqual(api.middleware_calls[0][1], 40)

    def test_release_plugin_loads_without_repository_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, _ = build(REPOSITORY_ROOT, root)
            extracted = root / "extracted"
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extracted)
            forbidden_root = json.dumps(str(REPOSITORY_ROOT.resolve()))
            script = (
                "import importlib.util,json,pathlib,sys,types;"
                "root=pathlib.Path.cwd();"
                "spec=importlib.util.spec_from_file_location('isolated_plugin',root/'plugin.py');"
                "mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);"
                "calls=[];middlewares=[];"
                "api=types.SimpleNamespace(register_tool=lambda **kw:calls.append(kw),"
                "register_middleware=lambda factory,priority=100:middlewares.append(priority));"
                "mod.plugin.register(api);"
                "print(json.dumps({'plugin':type(mod.plugin).__name__,'repo_on_path':"
                f"any(pathlib.Path(p).resolve()==pathlib.Path({forbidden_root}) for p in sys.path),"
                "'tool':calls[0]['tool_name'],'middleware_priority':middlewares[0]}))"
            )
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "PYTHONPATH": "",
            }
            completed = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=extracted,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["plugin"], "SenseNovaImageGenerationToolPlugin")
            self.assertFalse(result["repo_on_path"])
            self.assertEqual(result["tool"], "image_generation")
            self.assertEqual(result["middleware_priority"], 40)


if __name__ == "__main__":
    unittest.main()
