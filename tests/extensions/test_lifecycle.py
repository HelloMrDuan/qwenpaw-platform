import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.extensions.lifecycle import (
    ExtensionLifecycleManager,
    ExtensionState,
    InvalidLifecycleTransition,
    LifecycleVerificationError,
)
from scripts.build_extension import build_extension
from scripts.deploy_extension import deploy_extension
from scripts.extension_cli import main as extension_cli_main


class ExtensionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.extension_root = self.root / "plugins" / "lifecycle-fixture"
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
        self.manager = ExtensionLifecycleManager(self.deployments)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_install_enable_start_stop_disable_state_transitions(self) -> None:
        installed = self.manager.install(self.version_one.archive)
        enabled = self.manager.enable(installed.name)
        running = self.manager.start(installed.name)
        stopped = self.manager.stop(installed.name)
        disabled = self.manager.disable(installed.name)

        self.assertEqual(installed.state, ExtensionState.INSTALLED)
        self.assertEqual(enabled.state, ExtensionState.ENABLED)
        self.assertEqual(running.state, ExtensionState.RUNNING)
        self.assertEqual(stopped.state, ExtensionState.ENABLED)
        self.assertEqual(disabled.state, ExtensionState.DISABLED)
        self.assertEqual(disabled.revision, 5)
        self.assertFalse(
            (self.deployments / installed.name / "versions" / installed.version / "executed.txt").exists()
        )

    def test_disabled_extension_cannot_start_and_disable_is_idempotent(self) -> None:
        record = self.manager.install(self.version_one.archive)
        disabled = self.manager.disable(record.name)
        repeated = self.manager.disable(record.name)

        self.assertEqual(repeated, disabled)
        with self.assertRaisesRegex(InvalidLifecycleTransition, "cannot start"):
            self.manager.start(record.name)

    def test_health_reports_verified_state_and_marks_tampering_failed(self) -> None:
        record = self.manager.install(self.version_one.archive)
        self.manager.enable(record.name)
        healthy = self.manager.health(record.name)

        self.assertTrue(healthy.healthy)
        self.assertTrue(healthy.deployment_verified)
        self.assertFalse(healthy.runtime_probe_performed)
        self.assertEqual(healthy.code, "VERIFIED_ENABLED")

        entrypoint = self.deployments / record.name / "versions" / record.version / "entrypoint.py"
        entrypoint.write_text("TAMPERED = True\n", encoding="utf-8")
        failed = self.manager.health(record.name)

        self.assertFalse(failed.healthy)
        self.assertEqual(failed.code, "DEPLOYMENT_INVALID")
        self.assertEqual(self.manager.get(record.name).state, ExtensionState.FAILED)

    def test_verify_marks_failure_and_recovers_after_integrity_is_restored(self) -> None:
        record = self.manager.install(self.version_one.archive)
        verified = self.manager.verify(record.name)
        self.assertEqual(verified.state, ExtensionState.INSTALLED)
        self.assertEqual(verified.last_action.value, "verify")

        entrypoint = self.deployments / record.name / "versions" / record.version / "entrypoint.py"
        original = entrypoint.read_bytes()
        entrypoint.write_text("TAMPERED = True\n", encoding="utf-8")
        with self.assertRaises(LifecycleVerificationError):
            self.manager.verify(record.name)
        self.assertEqual(self.manager.get(record.name).state, ExtensionState.FAILED)

        entrypoint.write_bytes(original)
        recovered = self.manager.verify(record.name)
        self.assertEqual(recovered.state, ExtensionState.INSTALLED)
        self.assertIsNone(recovered.error)

    def test_disabled_health_is_not_healthy_but_integrity_is_verified(self) -> None:
        record = self.manager.install(self.version_one.archive)
        self.manager.disable(record.name)

        report = self.manager.health(record.name)

        self.assertFalse(report.healthy)
        self.assertTrue(report.deployment_verified)
        self.assertEqual(report.code, "DISABLED")

    def test_upgrade_and_rollback_never_restore_running_automatically(self) -> None:
        record = self.manager.install(self.version_one.archive)
        self.manager.enable(record.name)
        self.manager.start(record.name)

        upgraded = self.manager.upgrade(self.version_two.archive)
        self.assertEqual(upgraded.version, "1.1.0")
        self.assertEqual(upgraded.state, ExtensionState.ENABLED)
        self.manager.start(record.name)

        rolled_back = self.manager.rollback(record.name, version="1.0.0")

        self.assertEqual(rolled_back.version, "1.0.0")
        self.assertEqual(rolled_back.state, ExtensionState.ENABLED)
        current = json.loads(
            (self.deployments / record.name / "current.json").read_text(encoding="utf-8")
        )
        self.assertEqual(current["version"], "1.0.0")

    def test_list_and_cli_list_return_installed_lifecycle_records(self) -> None:
        installed = self.manager.install(self.version_one.archive)
        self.assertEqual([record.name for record in self.manager.list()], [installed.name])

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = extension_cli_main(
                ["--target", str(self.deployments), "list"]
            )
        document = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(document[0]["name"], installed.name)
        self.assertEqual(document[0]["state"], "INSTALLED")

    def test_install_adopts_an_existing_offline_deployment(self) -> None:
        deployed = deploy_extension(
            self.version_one.archive, target_root=self.deployments
        )
        lifecycle_path = deployed.current_pointer.with_name("lifecycle.json")
        self.assertFalse(lifecycle_path.exists())

        record = self.manager.install(self.version_one.archive)

        self.assertEqual(record.state, ExtensionState.INSTALLED)
        self.assertTrue(lifecycle_path.is_file())

    def _write_fixture(self, version: str) -> None:
        self.extension_root.mkdir(parents=True)
        (self.extension_root / "README.md").write_text(
            "# Lifecycle fixture\n", encoding="utf-8"
        )
        (self.extension_root / "entrypoint.py").write_text(
            "from pathlib import Path\n"
            "Path(__file__).with_name('executed.txt').write_text('executed')\n",
            encoding="utf-8",
        )
        self._write_manifest(version)

    def _write_manifest(self, version: str) -> None:
        manifest = {
            "name": "lifecycle-fixture",
            "type": "plugin",
            "version": version,
            "description": "Lifecycle test fixture.",
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
