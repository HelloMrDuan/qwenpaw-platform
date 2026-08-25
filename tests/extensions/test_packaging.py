import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_extension import (
    GENERATED_CONFIG_TEMPLATE_NAME,
    PACKAGE_SCHEMA_VERSION,
    RELEASE_INFO_NAME,
    build_extension,
)


class ExtensionPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary_directory.name)
        cls.extension_root = cls.root / "skills" / "fixture-skill"
        cls.output = cls.root / "dist" / "extensions"
        cls._write_fixture()
        cls.result = build_extension(
            cls.extension_root / "manifest.yaml",
            cls.output,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_package_structure_contains_required_and_source_files(self) -> None:
        with zipfile.ZipFile(self.result.archive) as package:
            names = set(package.namelist())

        self.assertIn("manifest.yaml", names)
        self.assertIn("README.md", names)
        self.assertIn("CHANGELOG.md", names)
        self.assertIn("executor/main.py", names)
        self.assertIn(".env.example", names)
        self.assertIn(RELEASE_INFO_NAME, names)
        self.assertIn(GENERATED_CONFIG_TEMPLATE_NAME, names)

    def test_secret_runtime_and_cache_files_are_excluded(self) -> None:
        with zipfile.ZipFile(self.result.archive) as package:
            names = set(package.namelist())

        self.assertNotIn(".env", names)
        self.assertNotIn("token", names)
        self.assertNotIn("runtime.db", names)
        self.assertNotIn("worker.log", names)
        self.assertNotIn("worker.pid", names)
        self.assertNotIn("__pycache__/main.pyc", names)
        self.assertNotIn("cache/state.json", names)
        self.assertNotIn("secrets/api-key", names)
        self.assertIn("executor/token_auth.py", names)
        self.assertIn("executor/secret_sources.py", names)

    def test_zip_can_be_extracted_and_release_info_matches_manifest(self) -> None:
        extraction_root = self.root / "extracted"
        with zipfile.ZipFile(self.result.archive) as package:
            package.extractall(extraction_root)

        manifest = json.loads((extraction_root / "manifest.yaml").read_text(encoding="utf-8"))
        release = json.loads(
            (extraction_root / RELEASE_INFO_NAME).read_text(encoding="utf-8")
        )
        generated_config = (
            extraction_root / GENERATED_CONFIG_TEMPLATE_NAME
        ).read_text(encoding="utf-8")
        self.assertEqual(manifest["name"], "fixture-skill")
        self.assertEqual(release["schema_version"], PACKAGE_SCHEMA_VERSION)
        self.assertEqual(release["name"], manifest["name"])
        self.assertEqual(release["type"], manifest["type"])
        self.assertEqual(release["version"], manifest["version"])
        self.assertEqual(
            release["generated_config_template"],
            GENERATED_CONFIG_TEMPLATE_NAME,
        )
        self.assertIn("No unconditional secrets", generated_config)

    def test_sha256_and_sidecar_are_generated(self) -> None:
        expected = hashlib.sha256(self.result.archive.read_bytes()).hexdigest()
        sidecar = self.result.archive.with_suffix(".zip.sha256")

        self.assertEqual(self.result.sha256, expected)
        self.assertTrue(sidecar.is_file())
        self.assertEqual(
            sidecar.read_text(encoding="utf-8"),
            f"{expected}  {self.result.archive.name}\n",
        )

    def test_same_input_produces_same_hash(self) -> None:
        second_output = self.root / "second-dist"
        second = build_extension(
            self.extension_root / "manifest.yaml",
            second_output,
        )
        self.assertEqual(second.sha256, self.result.sha256)

    def test_real_skill_plugin_and_adapter_manifests_can_be_packaged(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        manifests = {
            "skill": repository_root / "skills" / "pdf-editor" / "manifest.yaml",
            "plugin": repository_root / "plugins" / "wecom" / "manifest.yaml",
            "adapter": repository_root / "adapters" / "telegram" / "manifest.yaml",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            for extension_type, manifest in manifests.items():
                with self.subTest(extension_type=extension_type):
                    result = build_extension(manifest, output)
                    self.assertEqual(result.type, extension_type)
                    self.assertTrue(result.archive.name.endswith(f".{extension_type}.zip"))
                    with zipfile.ZipFile(result.archive) as package:
                        self.assertIn(GENERATED_CONFIG_TEMPLATE_NAME, package.namelist())

    @classmethod
    def _write_fixture(cls) -> None:
        (cls.extension_root / "executor").mkdir(parents=True)
        (cls.extension_root / "schemas").mkdir()
        (cls.extension_root / "tests").mkdir()
        (cls.extension_root / "__pycache__").mkdir()
        (cls.extension_root / "cache").mkdir()
        (cls.extension_root / "secrets").mkdir()

        manifest = {
            "name": "fixture-skill",
            "type": "skill",
            "version": "1.2.3",
            "description": "Packaging test fixture.",
            "executor": {
                "runtime": "python",
                "path": "executor/main.py",
                "callable": "execute",
            },
            "dependencies": [],
            "schemas": {
                "request": "schemas/request.schema.json",
                "result": "schemas/result.schema.json",
            },
            "artifacts": {
                "inputs": [
                    {
                        "name": "input_file",
                        "kind": "file",
                        "mime_types": ["application/pdf"],
                        "required": True,
                    }
                ],
                "outputs": [
                    {
                        "name": "output_file",
                        "kind": "file",
                        "mime_types": ["application/pdf"],
                        "required": True,
                    }
                ],
                "uri_scheme": "artifact",
            },
            "events": ["tool.start", "tool.result"],
            "tests": ["tests/test_executor.py"],
        }
        (cls.extension_root / "manifest.yaml").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        (cls.extension_root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        (cls.extension_root / "CHANGELOG.md").write_text(
            "# Changelog\n",
            encoding="utf-8",
        )
        (cls.extension_root / ".env.example").write_text(
            "SAFE_TEMPLATE=\n",
            encoding="utf-8",
        )
        (cls.extension_root / ".env").write_text("SECRET=value\n", encoding="utf-8")
        (cls.extension_root / "token").write_text("token-value\n", encoding="utf-8")
        (cls.extension_root / "runtime.db").write_bytes(b"database")
        (cls.extension_root / "worker.log").write_text("log\n", encoding="utf-8")
        (cls.extension_root / "worker.pid").write_text("1\n", encoding="utf-8")
        (cls.extension_root / "__pycache__" / "main.pyc").write_bytes(b"cache")
        (cls.extension_root / "cache" / "state.json").write_text("{}", encoding="utf-8")
        (cls.extension_root / "secrets" / "api-key").write_text(
            "secret-value\n",
            encoding="utf-8",
        )
        (cls.extension_root / "executor" / "main.py").write_text(
            "def execute():\n    return None\n",
            encoding="utf-8",
        )
        (cls.extension_root / "executor" / "token_auth.py").write_text(
            "TOKEN_FIELD = 'token'\n",
            encoding="utf-8",
        )
        (cls.extension_root / "executor" / "secret_sources.py").write_text(
            "def sources():\n    return ()\n",
            encoding="utf-8",
        )
        for schema_name in ("request", "result"):
            (cls.extension_root / "schemas" / f"{schema_name}.schema.json").write_text(
                "{}",
                encoding="utf-8",
            )
        (cls.extension_root / "tests" / "test_executor.py").write_text(
            "# fixture test\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
