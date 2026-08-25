import json
import re
import unittest
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "extension-manifest.schema.json"
MANIFEST_PATHS = (
    REPOSITORY_ROOT / "plugins" / "hermes" / "manifest.yaml",
    REPOSITORY_ROOT / "plugins" / "wecom" / "manifest.yaml",
    REPOSITORY_ROOT / "plugins" / "wechat-customer" / "manifest.yaml",
    REPOSITORY_ROOT / "plugins" / "wechat-mp" / "manifest.yaml",
    REPOSITORY_ROOT / "adapters" / "telegram" / "manifest.yaml",
    REPOSITORY_ROOT / "skills" / "pdf-editor" / "manifest.yaml",
)


class ExtensionManifestValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = cls._load_json_document(SCHEMA_PATH)
        cls.manifests = {
            path: cls._load_json_document(path) for path in MANIFEST_PATHS
        }

    @staticmethod
    def _load_json_document(path: Path) -> dict:
        """Load the repository's JSON-compatible YAML 1.2 profile."""
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        if not isinstance(document, dict):
            raise AssertionError(f"{path} must contain a mapping")
        return document

    def test_yaml_format_and_expected_manifest_set(self) -> None:
        self.assertEqual(len(self.manifests), 6)
        for path, manifest in self.manifests.items():
            self.assertEqual(path.suffix, ".yaml")
            self.assertIsInstance(manifest, dict)

    def test_required_fields_and_no_unknown_fields(self) -> None:
        common = set(self.schema["required"])
        runtime_fields = common | {
            "runtime",
            "entrypoint",
            "dependencies",
            "config_template",
            "healthcheck",
            "ports",
            "required_secrets",
        }
        skill_fields = common | {
            "executor",
            "dependencies",
            "schemas",
            "artifacts",
            "events",
            "tests",
        }
        for path, manifest in self.manifests.items():
            with self.subTest(path=path):
                required = skill_fields if manifest["type"] == "skill" else runtime_fields
                self.assertEqual(required - set(manifest), set())
                self.assertEqual(set(manifest) - required, set())
                self.assertTrue(manifest["description"].strip())
                self.assertRegex(
                    manifest["name"],
                    self.schema["properties"]["name"]["pattern"],
                )
                self.assertRegex(
                    manifest["version"],
                    self.schema["properties"]["version"]["pattern"],
                )

    def test_type_runtime_and_directory_are_consistent(self) -> None:
        allowed_types = set(self.schema["properties"]["type"]["enum"])
        allowed_runtimes = set(self.schema["properties"]["runtime"]["enum"])
        expected_parent_for_type = {
            "plugin": "plugins",
            "adapter": "adapters",
            "skill": "skills",
        }

        for path, manifest in self.manifests.items():
            with self.subTest(path=path):
                self.assertIn(manifest["type"], allowed_types)
                runtime = (
                    manifest["executor"]["runtime"]
                    if manifest["type"] == "skill"
                    else manifest["runtime"]
                )
                self.assertIn(runtime, allowed_runtimes)
                self.assertEqual(path.parent.name, manifest["name"])
                self.assertEqual(
                    path.parent.parent.name,
                    expected_parent_for_type[manifest["type"]],
                )

    def test_declared_paths_exist_and_cannot_escape_extension(self) -> None:
        for path, manifest in self.manifests.items():
            with self.subTest(path=path):
                if manifest["type"] == "skill":
                    self._assert_relative_existing_path(
                        path.parent,
                        manifest["executor"]["path"],
                    )
                    for schema_path in manifest["schemas"].values():
                        self._assert_relative_existing_path(path.parent, schema_path)
                    for test_path in manifest["tests"]:
                        self._assert_relative_existing_path(path.parent, test_path)
                    continue

                self._assert_relative_existing_path(path.parent, manifest["entrypoint"])

                config_template = manifest["config_template"]
                if config_template is not None:
                    self._assert_relative_existing_path(path.parent, config_template)

                healthcheck = manifest["healthcheck"]
                if healthcheck is not None and healthcheck["type"] == "command":
                    self._assert_relative_existing_path(
                        path.parent,
                        healthcheck["target"],
                    )

    def test_healthcheck_ports_dependencies_and_secrets(self) -> None:
        secret_pattern = re.compile(
            self.schema["properties"]["required_secrets"]["items"]["pattern"]
        )
        for path, manifest in self.manifests.items():
            with self.subTest(path=path):
                self.assertEqual(len(manifest["dependencies"]), len(set(manifest["dependencies"])))
                self.assertTrue(all(item.strip() for item in manifest["dependencies"]))

                if manifest["type"] == "skill":
                    continue

                ports = manifest["ports"]
                self.assertEqual(len(ports), len(set(ports)))
                self.assertTrue(all(type(port) is int and 1 <= port <= 65535 for port in ports))

                secrets = manifest["required_secrets"]
                self.assertEqual(len(secrets), len(set(secrets)))
                self.assertTrue(all(secret_pattern.fullmatch(secret) for secret in secrets))

                healthcheck = manifest["healthcheck"]
                if healthcheck is not None:
                    self.assertEqual(set(healthcheck), {"type", "target"})
                    self.assertIn(healthcheck["type"], {"http", "command"})
                    if healthcheck["type"] == "http":
                        parsed = urlparse(healthcheck["target"])
                        self.assertIn(parsed.scheme, {"http", "https"})
                        self.assertTrue(parsed.hostname)

    def test_schema_defines_all_requested_contract_fields(self) -> None:
        self.assertEqual(
            set(self.schema["required"]),
            {"name", "type", "version", "description"},
        )
        self.assertEqual(
            set(self.schema["properties"]["type"]["enum"]),
            {"plugin", "adapter", "skill"},
        )
        self.assertTrue(
            {
                "runtime",
                "entrypoint",
                "dependencies",
                "config_template",
                "healthcheck",
                "ports",
                "required_secrets",
                "executor",
                "schemas",
                "artifacts",
                "events",
                "tests",
            }.issubset(self.schema["properties"])
        )
        self.assertEqual(len(self.schema["allOf"]), 2)
        self.assertFalse(self.schema["additionalProperties"])

    def _assert_relative_existing_path(self, extension_root: Path, value: str) -> None:
        relative = PurePosixPath(value)
        self.assertFalse(relative.is_absolute())
        self.assertNotIn("..", relative.parts)
        self.assertNotRegex(value, r"^[A-Za-z]:")

        resolved_root = extension_root.resolve()
        resolved_target = (extension_root / Path(*relative.parts)).resolve()
        self.assertTrue(resolved_target.is_relative_to(resolved_root))
        self.assertTrue(resolved_target.is_file(), f"missing declared path: {resolved_target}")


if __name__ == "__main__":
    unittest.main()
