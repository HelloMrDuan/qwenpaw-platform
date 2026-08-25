import json
import tempfile
import unittest
from pathlib import Path

from core.extensions import (
    DuplicateExtensionError,
    ExtensionLoader,
    ExtensionMetadata,
    ExtensionRegistry,
    ExtensionRuntime,
    ExtensionType,
    ManifestValidationError,
    MissingManifestError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ExtensionRegistryTests(unittest.TestCase):
    def test_discovers_repository_manifests_without_loading_entrypoints(self) -> None:
        registry = ExtensionRegistry(REPOSITORY_ROOT)

        discovered = registry.discover()

        self.assertEqual(
            {metadata.name for metadata in discovered},
            {"hermes", "wecom", "wechat-customer", "wechat-mp", "telegram"},
        )
        self.assertEqual(len(registry.list(ExtensionType.PLUGIN)), 4)
        self.assertEqual(len(registry.list(ExtensionType.ADAPTER)), 1)
        self.assertEqual(registry.list(ExtensionType.SKILL), ())

    def test_loader_rejects_manifest_type_that_disagrees_with_directory(self) -> None:
        loader = ExtensionLoader()
        manifest_path = REPOSITORY_ROOT / "plugins" / "hermes" / "manifest.yaml"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        with self.assertRaisesRegex(ManifestValidationError, "does not match adapter"):
            loader.validate_manifest(
                manifest,
                manifest_path=manifest_path,
                expected_type=ExtensionType.ADAPTER,
            )

        malformed = dict(manifest)
        malformed["type"] = ["plugin"]
        with self.assertRaisesRegex(ManifestValidationError, "unsupported extension type"):
            loader.validate_manifest(malformed)

    def test_duplicate_names_are_rejected_without_overwrite(self) -> None:
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        metadata = self.make_metadata("duplicate")
        registry.register(metadata)

        with self.assertRaisesRegex(DuplicateExtensionError, "duplicate"):
            registry.register(self.make_metadata("duplicate"))

        self.assertIs(registry.get("duplicate"), metadata)

    def test_strict_discovery_detects_missing_manifest_before_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "plugins" / "missing-plugin").mkdir(parents=True)
            registry = ExtensionRegistry(root)

            with self.assertRaisesRegex(MissingManifestError, "missing-plugin"):
                registry.discover(strict=True)

            self.assertEqual(registry.list(), ())

    def test_registry_get_list_and_type_filter_are_stable(self) -> None:
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.register(self.make_metadata("zeta", ExtensionType.PLUGIN))
        registry.register(self.make_metadata("alpha", ExtensionType.ADAPTER))

        self.assertEqual([item.name for item in registry.list()], ["alpha", "zeta"])
        self.assertEqual(
            [item.name for item in registry.list("plugin")],
            ["zeta"],
        )
        self.assertEqual(registry.get("alpha").runtime, ExtensionRuntime.PYTHON)
        self.assertIsNone(registry.get("unknown"))

    def test_discovery_never_executes_declared_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            extension_root = root / "plugins" / "passive"
            extension_root.mkdir(parents=True)
            sentinel = root / "entrypoint-executed"
            entrypoint = extension_root / "entrypoint.py"
            entrypoint.write_text(
                f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n",
                encoding="utf-8",
            )
            self.write_manifest(extension_root / "manifest.yaml")

            registry = ExtensionRegistry(root)
            registry.discover()

            self.assertIsNotNone(registry.get("passive"))
            self.assertFalse(sentinel.exists())

    @staticmethod
    def make_metadata(
        name: str,
        extension_type: ExtensionType = ExtensionType.PLUGIN,
    ) -> ExtensionMetadata:
        return ExtensionMetadata(
            name=name,
            type=extension_type,
            version="1.0.0",
            runtime=ExtensionRuntime.PYTHON,
            entrypoint="entrypoint.py",
            healthcheck=None,
            dependencies=(),
        )

    @staticmethod
    def write_manifest(path: Path) -> None:
        manifest = {
            "name": "passive",
            "type": "plugin",
            "version": "1.0.0",
            "description": "Offline test extension.",
            "runtime": "python",
            "entrypoint": "entrypoint.py",
            "dependencies": [],
            "config_template": None,
            "healthcheck": None,
            "ports": [],
            "required_secrets": [],
        }
        path.write_text(json.dumps(manifest), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
