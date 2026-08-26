from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.build_extension import build_qwenpaw_plugins


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_CASES = {
    "telegram-channel-plugin": {
        "plugin_id": "telegram-extension-channel",
        "extension_name": "telegram",
        "extension_type": "adapter",
        "adapter": "adapter/telegram/runtime.py",
        "adapter_module": "telegram",
        "namespace": "qwenpaw_plugin_telegram_extension_channel",
        "manifest": "adapters/telegram/manifest.yaml",
        "declared_entrypoint": (
            "adapters/telegram/recovered/telegram_bridge_main.py"
        ),
    },
    "wecom-channel-plugin": {
        "plugin_id": "wecom-extension-channel",
        "extension_name": "wecom",
        "extension_type": "plugin",
        "adapter": "adapter/wecom/runtime.py",
        "adapter_module": "wecom",
        "namespace": "qwenpaw_plugin_wecom_extension_channel",
        "manifest": "plugins/wecom/manifest.yaml",
        "declared_entrypoint": (
            "plugins/wecom/recovered/wecom-node/wecom_bridge.mjs"
        ),
    },
    "wechat-customer-channel-plugin": {
        "plugin_id": "wechat-customer-extension-channel",
        "extension_name": "wechat-customer",
        "extension_type": "plugin",
        "adapter": "adapter/wechat_customer/runtime.py",
        "adapter_module": "wechat_customer",
        "namespace": "qwenpaw_plugin_wechat_customer_extension_channel",
        "manifest": "plugins/wechat-customer/manifest.yaml",
        "declared_entrypoint": (
            "plugins/wechat-customer/recovered/wecom_kf_gateway_v345.py"
        ),
    },
}


class SelfContainedPluginPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary_directory.name)
        cls.output = cls.root / "dist"
        cls.results = build_qwenpaw_plugins(
            REPOSITORY_ROOT,
            cls.output,
            names=tuple(PLUGIN_CASES),
        )
        cls.results_by_name = {result.name: result for result in cls.results}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_archives_contain_official_root_and_runtime_dependency_closure(self) -> None:
        shared = {
            "plugin.json",
            "plugin.py",
            "README.md",
            "runtime/__init__.py",
            "runtime/wrapper.py",
            "contracts/__init__.py",
            "core/contracts/__init__.py",
            "core/extensions/loader.py",
            "core/extensions/runtime/gateway.py",
            "core/extensions/runtime/plugin_bridge.py",
            "core/streaming/__init__.py",
            "schemas/extension-manifest.schema.json",
            "scripts/build_extension.py",
            "scripts/deploy_extension.py",
            "scripts/rollback_extension.py",
            "scripts/verify_extension.py",
        }
        for source_name, case in PLUGIN_CASES.items():
            with self.subTest(plugin=source_name):
                result = self.results_by_name[case["plugin_id"]]
                with zipfile.ZipFile(result.archive) as package:
                    names = set(package.namelist())
                    document = json.loads(package.read("plugin.json"))
                self.assertTrue(shared.issubset(names))
                self.assertIn(case["adapter"], names)
                self.assertIn(
                    f'{case["namespace"]}/{case["adapter"]}',
                    names,
                )
                self.assertIn(f'{case["namespace"]}/core/__init__.py', names)
                self.assertIn(f'{case["namespace"]}/runtime/wrapper.py', names)
                self.assertIn(case["manifest"], names)
                self.assertIn(case["declared_entrypoint"], names)
                self.assertEqual(document["id"], case["plugin_id"])
                self.assertEqual(document["version"], result.version)
                self.assertEqual(
                    document["meta"]["extension"]["adapter_entrypoint"],
                    case["adapter"],
                )
                self.assertTrue(
                    document["meta"]["extension"][
                        "source_adapter_entrypoint"
                    ].startswith("adapters/")
                )
                self.assertTrue(document["meta"]["permissions"])
                self.assertEqual(document["meta"]["config"]["values"], {})

    def test_packaged_entries_use_internal_adapter_and_wrapper_imports(self) -> None:
        for source_name, case in PLUGIN_CASES.items():
            with self.subTest(plugin=source_name):
                source_entry = (
                    REPOSITORY_ROOT / "plugins" / source_name / "plugin.py"
                ).read_text(encoding="utf-8")
                result = self.results_by_name[case["plugin_id"]]
                with zipfile.ZipFile(result.archive) as package:
                    packaged_entry = package.read("plugin.py").decode("utf-8")
                self.assertNotIn("from adapters.", source_entry)
                self.assertNotIn("from adapters.", packaged_entry)
                self.assertNotIn("sys.path.insert", packaged_entry)
                self.assertIn(
                    f'from {case["namespace"]}.adapter.',
                    packaged_entry,
                )
                self.assertIn(
                    f'from {case["namespace"]}.runtime.wrapper import',
                    packaged_entry,
                )

    def test_isolated_import_and_internal_manifest_loading_succeed(self) -> None:
        probe = "\n".join(
            (
                "import importlib.util",
                "import importlib",
                "import json",
                "from pathlib import Path",
                "import sys",
                "entry = Path(sys.argv[1]).resolve()",
                "repository = Path(sys.argv[2]).resolve()",
                "adapter_name = sys.argv[3]",
                "adapter_package = importlib.import_module(f'adapter.{adapter_name}')",
                "spec = importlib.util.spec_from_file_location('isolated_plugin', entry)",
                "module = importlib.util.module_from_spec(spec)",
                "sys.modules[spec.name] = module",
                "spec.loader.exec_module(module)",
                "metadata = module.plugin.load_extension_manifest()",
                "payload = {",
                "  'name': metadata.name,",
                "  'type': metadata.type.value,",
                "  'version': metadata.version,",
                "  'self_contained': module.SELF_CONTAINED,",
                "  'runtime_root': str(module.REPOSITORY_ROOT.resolve()),",
                "  'adapter_module': module.__dict__[next(name for name in module.__dict__ if name.endswith('RuntimeAdapter'))].__module__,",
                "  'wrapper_module': module.OfficialPluginRuntimeWrapper.__module__,",
                "  'repository_on_sys_path': str(repository) in sys.path,",
                "  'plugin_root_on_sys_path': str(entry.parent) in sys.path,",
                "  'direct_adapter': adapter_package.__name__,",
                "  'sys_path': [str(Path(item).resolve()) for item in sys.path if item],",
                "}",
                "print(json.dumps(payload))",
            )
        )
        for source_name, case in PLUGIN_CASES.items():
            with self.subTest(plugin=source_name):
                result = self.results_by_name[case["plugin_id"]]
                extraction_root = self.root / f"extract-{source_name}"
                with zipfile.ZipFile(result.archive) as package:
                    package.extractall(extraction_root)
                empty_cwd = self.root / f"cwd-{source_name}"
                empty_cwd.mkdir()
                environment = os.environ.copy()
                environment["PYTHONPATH"] = str(extraction_root)
                environment.pop("PYTHONHOME", None)
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-S",
                        "-c",
                        probe,
                        str(extraction_root / "plugin.py"),
                        str(REPOSITORY_ROOT),
                        case["adapter_module"],
                    ],
                    cwd=empty_cwd,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["name"], case["extension_name"])
                self.assertEqual(payload["type"], case["extension_type"])
                self.assertEqual(payload["version"], "0.1.0-recovered")
                self.assertTrue(payload["self_contained"])
                self.assertEqual(
                    Path(payload["runtime_root"]).resolve(),
                    extraction_root.resolve(),
                )
                self.assertTrue(
                    payload["adapter_module"].startswith(f'{case["namespace"]}.')
                )
                self.assertEqual(
                    payload["wrapper_module"],
                    f'{case["namespace"]}.runtime.wrapper',
                )
                self.assertFalse(payload["repository_on_sys_path"])
                self.assertTrue(payload["plugin_root_on_sys_path"])
                self.assertEqual(
                    payload["direct_adapter"],
                    f'adapter.{case["adapter_module"]}',
                )
                self.assertNotIn(str(REPOSITORY_ROOT.resolve()), payload["sys_path"])

    def test_all_entries_load_in_one_isolated_process_without_namespace_collision(self) -> None:
        extraction_roots: list[Path] = []
        for source_name, case in PLUGIN_CASES.items():
            result = self.results_by_name[case["plugin_id"]]
            extraction_root = self.root / f"shared-{source_name}"
            with zipfile.ZipFile(result.archive) as package:
                package.extractall(extraction_root)
            extraction_roots.append(extraction_root)

        probe = "\n".join(
            (
                "import importlib.util",
                "import json",
                "from pathlib import Path",
                "import sys",
                "repository = Path(sys.argv[1]).resolve()",
                "telegram_adapter = Path(sys.argv[2]).resolve() / 'adapter'",
                "adapter_spec = importlib.util.spec_from_file_location('adapter', telegram_adapter / '__init__.py', submodule_search_locations=[str(telegram_adapter)])",
                "adapter_package = importlib.util.module_from_spec(adapter_spec)",
                "sys.modules['adapter'] = adapter_package",
                "adapter_spec.loader.exec_module(adapter_package)",
                "loaded = []",
                "for index, raw_root in enumerate(sys.argv[2:]):",
                "  root = Path(raw_root).resolve()",
                "  spec = importlib.util.spec_from_file_location(f'qwenpaw_shared_{index}', root / 'plugin.py')",
                "  module = importlib.util.module_from_spec(spec)",
                "  sys.modules[spec.name] = module",
                "  spec.loader.exec_module(module)",
                "  adapter = module.__dict__[next(name for name in module.__dict__ if name.endswith('RuntimeAdapter'))]",
                "  loaded.append({'extension': module.plugin.extension_id, 'adapter_module': adapter.__module__})",
                "print(json.dumps({'loaded': loaded, 'repository_on_sys_path': str(repository) in sys.path, 'cached_adapter_path': list(adapter_package.__path__)}))",
            )
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                probe,
                str(REPOSITORY_ROOT),
                *(str(root) for root in extraction_roots),
            ],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["repository_on_sys_path"])
        self.assertEqual(
            [Path(item).resolve() for item in payload["cached_adapter_path"]],
            [(extraction_roots[0] / "adapter").resolve()],
        )
        self.assertEqual(
            [item["extension"] for item in payload["loaded"]],
            ["telegram", "wecom", "wechat-customer"],
        )
        self.assertEqual(
            [item["adapter_module"] for item in payload["loaded"]],
            [
                f'{case["namespace"]}.adapter.{case["adapter_module"]}.runtime'
                for case in PLUGIN_CASES.values()
            ],
        )

    def test_release_python_does_not_mutate_sys_path(self) -> None:
        for case in PLUGIN_CASES.values():
            with self.subTest(plugin=case["plugin_id"]):
                result = self.results_by_name[case["plugin_id"]]
                with zipfile.ZipFile(result.archive) as package:
                    offenders = [
                        name
                        for name in package.namelist()
                        if name.endswith(".py")
                        and b"sys.path.insert" in package.read(name)
                    ]
                self.assertEqual(offenders, [])

    def test_build_is_deterministic_and_excludes_runtime_state(self) -> None:
        second_output = self.root / "second-dist"
        second = build_qwenpaw_plugins(
            REPOSITORY_ROOT,
            second_output,
            names=tuple(PLUGIN_CASES),
        )
        second_by_name = {result.name: result for result in second}
        forbidden_names = {
            ".env",
            "credentials.yaml",
            "runtime.db",
            "gateway.db",
            "worker.log",
        }
        for case in PLUGIN_CASES.values():
            with self.subTest(plugin=case["plugin_id"]):
                first = self.results_by_name[case["plugin_id"]]
                self.assertEqual(first.sha256, second_by_name[first.name].sha256)
                with zipfile.ZipFile(first.archive) as package:
                    names = set(package.namelist())
                self.assertFalse(forbidden_names.intersection(names))
                self.assertFalse(
                    any(
                        "__pycache__" in name
                        or name.endswith((".pyc", ".db", ".log", ".token"))
                        for name in names
                    )
                )


if __name__ == "__main__":
    unittest.main()
