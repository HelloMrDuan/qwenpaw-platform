import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_extension import build_extension, sha256_file
from scripts.deploy_extension import ExtensionDeploymentError, deploy_extension
from scripts.rollback_extension import rollback_extension
from scripts.verify_extension import (
    ExtensionVerificationError,
    verify_deployment,
    verify_package,
)


class ExtensionDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.extension_root = self.root / "plugins" / "fixture-plugin"
        self.output = self.root / "dist"
        self.deployments = self.root / "workspace" / "extensions"
        self._write_fixture("1.0.0")
        self.version_one = build_extension(
            self.extension_root / "manifest.yaml", self.output
        )
        self._write_manifest("1.1.0")
        self.version_two = build_extension(
            self.extension_root / "manifest.yaml", self.output
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_install_creates_verified_version_and_active_pointer(self) -> None:
        result = deploy_extension(
            self.version_one.archive, target_root=self.deployments
        )

        self.assertTrue(result.installed)
        self.assertEqual(result.version, "1.0.0")
        self.assertTrue((result.version_directory / "manifest.yaml").is_file())
        self.assertFalse((result.version_directory / "executed.txt").exists())
        current = json.loads(result.current_pointer.read_text(encoding="utf-8"))
        self.assertEqual(current["version"], "1.0.0")
        self.assertEqual(current["relative_path"], "versions/1.0.0")
        verified = verify_deployment(result.version_directory)
        self.assertEqual(verified.package_sha256, self.version_one.sha256)

    def test_same_package_install_is_idempotent(self) -> None:
        first = deploy_extension(self.version_one.archive, target_root=self.deployments)
        second = deploy_extension(self.version_one.archive, target_root=self.deployments)

        self.assertTrue(first.installed)
        self.assertFalse(second.installed)
        history = json.loads(
            (self.deployments / "fixture-plugin" / "history.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(history["activations"]), 1)

    def test_verify_rejects_wrong_sha256(self) -> None:
        with self.assertRaisesRegex(ExtensionVerificationError, "SHA256 mismatch"):
            verify_package(self.version_one.archive, expected_sha256="0" * 64)

    def test_deployment_verification_detects_tampering(self) -> None:
        result = deploy_extension(self.version_one.archive, target_root=self.deployments)
        (result.version_directory / "entrypoint.py").write_text(
            "TAMPERED = True\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(
            ExtensionVerificationError, "deployed file hash mismatch"
        ):
            verify_deployment(result.version_directory)

    def test_install_rejects_unsafe_zip_path(self) -> None:
        unsafe = self.output / "unsafe.plugin.zip"
        with zipfile.ZipFile(self.version_one.archive) as source, zipfile.ZipFile(
            unsafe, "w"
        ) as destination:
            for info in source.infolist():
                destination.writestr(info, source.read(info))
            destination.writestr("../escape.txt", "unsafe")

        with self.assertRaisesRegex(ExtensionDeploymentError, "unsafe ZIP path"):
            deploy_extension(
                unsafe,
                target_root=self.deployments,
                expected_sha256=sha256_file(unsafe),
            )
        self.assertFalse((self.root / "escape.txt").exists())

    def test_install_two_versions_and_rollback(self) -> None:
        deploy_extension(self.version_one.archive, target_root=self.deployments)
        deploy_extension(self.version_two.archive, target_root=self.deployments)

        result = rollback_extension(
            "fixture-plugin", version="1.0.0", target_root=self.deployments
        )

        self.assertEqual(result.from_version, "1.1.0")
        self.assertEqual(result.to_version, "1.0.0")
        current = json.loads(
            (self.deployments / "fixture-plugin" / "current.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(current["version"], "1.0.0")
        self.assertTrue(
            (self.deployments / "fixture-plugin" / "versions" / "1.1.0").is_dir()
        )
        self.assertEqual(verify_deployment(result.version_directory).version, "1.0.0")

    def _write_fixture(self, version: str) -> None:
        self.extension_root.mkdir(parents=True)
        (self.extension_root / "README.md").write_text(
            "# Fixture plugin\n", encoding="utf-8"
        )
        (self.extension_root / "entrypoint.py").write_text(
            "from pathlib import Path\n"
            "Path(__file__).with_name('executed.txt').write_text('executed')\n",
            encoding="utf-8",
        )
        self._write_manifest(version)

    def _write_manifest(self, version: str) -> None:
        manifest = {
            "name": "fixture-plugin",
            "type": "plugin",
            "version": version,
            "description": "Offline deployment test fixture.",
            "runtime": "python",
            "entrypoint": "entrypoint.py",
            "dependencies": [],
            "config_template": None,
            "healthcheck": None,
            "ports": [],
            "required_secrets": [],
        }
        (self.extension_root / "manifest.yaml").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
