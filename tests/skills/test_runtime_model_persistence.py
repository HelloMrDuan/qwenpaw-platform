from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.productivity_skills.runtime import (
    FasterWhisperAdapter,
    FasterWhisperConfig,
    RembgConfig,
)
from core.productivity_skills.runtime.config import RuntimePaths
from scripts.normalize_runtime_models import inspect_models, link_models


class RuntimeModelPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.home = self.root / "home"
        self.workspace.mkdir()
        self.home.mkdir()
        self.environment = {
            "QWENPAW_WORKSPACE": str(self.workspace),
            "QWENPAW_ASR_MODEL": "tiny",
            "QWENPAW_REMBG_MODEL": "u2netp",
            "QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD": "0",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def env(self, extra=None):
        values = dict(self.environment)
        values.update(extra or {})
        return patch.dict(os.environ, values, clear=True)

    @staticmethod
    def make_asr_model(path: Path):
        path.mkdir(parents=True)
        (path / "model.bin").write_bytes(b"model")
        (path / "config.json").write_text("{}", encoding="utf-8")
        return path

    @staticmethod
    def make_rembg_model(root: Path):
        path = root / "u2netp" / "u2netp.onnx"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"onnx")
        return path

    def home_patch(self):
        return patch(
            "core.productivity_skills.runtime.config.Path.home",
            return_value=self.home,
        )

    def test_01_asr_discovers_workspace_model(self):
        expected = self.make_asr_model(
            self.workspace / ".runtime" / "models" / "asr" / "tiny"
        )
        with self.env(), self.home_patch():
            discovered = FasterWhisperConfig.from_env().discover_model()
        self.assertEqual(discovered, expected)

    def test_02_asr_discovers_huggingface_standard_cache(self):
        expected = self.make_asr_model(
            self.home
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--Systran--faster-whisper-tiny"
            / "snapshots"
            / "runtime-generated-hash"
        )
        with self.env(), self.home_patch():
            discovered = FasterWhisperConfig.from_env().discover_model()
        self.assertEqual(discovered, expected)

    def test_03_asr_snapshot_discovery_does_not_depend_on_hash(self):
        snapshots = (
            self.home
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--Systran--faster-whisper-tiny"
            / "snapshots"
        )
        expected = self.make_asr_model(snapshots / "another-unpredictable-snapshot")
        with self.env(), self.home_patch():
            config = FasterWhisperConfig.from_env()
            self.assertEqual(config.discover_model(), expected)

    def test_04_download_disabled_existing_model_is_available(self):
        expected = self.make_asr_model(
            self.workspace / ".runtime" / "models" / "asr" / "tiny"
        )

        class Model:
            pass

        with self.env(), self.home_patch():
            adapter = FasterWhisperAdapter(
                FasterWhisperConfig.from_env(),
                model_factory=lambda reference, **kwargs: Model(),
            )
            health = adapter.healthcheck(load_model=True)
        self.assertEqual(adapter.config.reference, str(expected))
        self.assertEqual(health["status"], "AVAILABLE")
        self.assertEqual(health["runtime_test"], "model_load_pass")

    def test_05_download_disabled_without_model_is_degraded(self):
        with self.env(), self.home_patch():
            health = FasterWhisperAdapter(
                FasterWhisperConfig.from_env(),
                model_factory=lambda *args, **kwargs: object(),
            ).healthcheck(load_model=True)
        self.assertEqual(health["status"], "DEGRADED")
        self.assertEqual(health["runtime_test"], "model_missing")

    def test_06_rembg_discovers_nested_model_from_root(self):
        model_root = self.root / "rembg-root"
        expected = self.make_rembg_model(model_root)
        with self.env({"QWENPAW_REMBG_MODEL_DIR": str(model_root)}), self.home_patch():
            config = RembgConfig.from_env()
            self.assertEqual(config.discover_model_file(), expected)

    def test_07_rembg_discovers_workspace_model(self):
        expected = self.make_rembg_model(
            self.workspace / ".runtime" / "models" / "rembg"
        )
        with self.env(), self.home_patch():
            config = RembgConfig.from_env()
            self.assertEqual(config.discover_model_file(), expected)

    def test_08_rembg_discovers_home_cache(self):
        expected = self.make_rembg_model(self.home / ".rembg" / "models")
        with self.env(), self.home_patch():
            config = RembgConfig.from_env()
            self.assertEqual(config.discover_model_file(), expected)

    def test_09_rembg_environment_points_to_models_root(self):
        configured_root = self.root / "configured-rembg-models"
        expected = self.make_rembg_model(configured_root)
        with self.env({"QWENPAW_REMBG_MODEL_DIR": str(configured_root)}), self.home_patch():
            config = RembgConfig.from_env()
        self.assertEqual(config.discover_model_file(), expected)
        self.assertEqual(config.discovered_model_root(), configured_root)
        self.assertEqual(config.discovered_model_dir(), configured_root / "u2netp")

    def test_10_runtime_source_has_no_hardcoded_root_path(self):
        source = Path(__file__).parents[2] / "core" / "productivity_skills" / "runtime"
        content = "\n".join(path.read_text(encoding="utf-8") for path in source.glob("*.py"))
        self.assertNotIn("/root/", content)

    def test_11_runtime_source_has_no_nas_workspace_identifier(self):
        source = Path(__file__).parents[2] / "core" / "productivity_skills" / "runtime"
        content = "\n".join(path.read_text(encoding="utf-8") for path in source.glob("*.py"))
        self.assertNotRegex(content, r"/run/csi|workspace-[0-9a-f]{6,}|pvc-[0-9a-f]{6,}")

    def test_12_normalize_inspect_does_not_modify_files(self):
        self.make_asr_model(
            self.home
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--Systran--faster-whisper-tiny"
            / "snapshots"
            / "hash"
        )
        self.make_rembg_model(self.home / ".rembg" / "models")
        target_root = self.workspace / ".runtime"
        with self.env(), self.home_patch():
            locations = inspect_models()
        self.assertEqual({item.status for item in locations}, {"FOUND"})
        self.assertTrue(all(item.needs_migration for item in locations))
        self.assertFalse(target_root.exists())

    def test_13_normalize_link_creates_links_or_degrades_safely(self):
        self.make_asr_model(
            self.home
            / ".cache"
            / "huggingface"
            / "hub"
            / "models--Systran--faster-whisper-tiny"
            / "snapshots"
            / "hash"
        )
        self.make_rembg_model(self.home / ".rembg" / "models")
        with self.env(), self.home_patch():
            linked = link_models(inspect_models())
        self.assertTrue(
            all(item.status in {"LINKED", "LINK_UNSUPPORTED"} for item in linked)
        )
        for item in linked:
            target = Path(item.target)
            if item.status == "LINKED":
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.resolve(), Path(item.source).resolve())
            else:
                self.assertFalse(target.is_symlink())


if __name__ == "__main__":
    unittest.main()
