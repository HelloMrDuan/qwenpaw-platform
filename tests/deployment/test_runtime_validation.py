from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.deployment import (
    AgentScopeDeploymentAdapter,
    AgentScopeDeploymentBridgeError,
    RollbackAction,
)
from scripts.build_extension import build_extension
from scripts.generate_install_report import (
    INSTALL_REPORT_SCHEMA_VERSION,
    RUNTIME_DISCOVERY_STATUS,
    InstallReportError,
    generate_install_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class AgentScopeRuntimeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary_directory.name)
        cls.output = cls.root / "dist"
        cls.workspace = cls.root / "agentscope-workspace"
        cls.packages = {
            "pdf-editor": build_extension(
                REPOSITORY_ROOT / "skills" / "pdf-editor" / "manifest.yaml",
                cls.output,
            ),
            "wecom": build_extension(
                REPOSITORY_ROOT / "plugins" / "wecom" / "manifest.yaml",
                cls.output,
            ),
            "telegram": build_extension(
                REPOSITORY_ROOT / "adapters" / "telegram" / "manifest.yaml",
                cls.output,
            ),
        }
        cls.rollback_root = cls.root / "plugins" / "rollback-fixture"
        cls._write_rollback_fixture("1.0.0")
        cls.rollback_package = build_extension(
            cls.rollback_root / "manifest.yaml",
            cls.output,
        )
        cls._write_rollback_manifest("1.1.0")
        cls.current_package = build_extension(
            cls.rollback_root / "manifest.yaml",
            cls.output,
        )
        cls.adapter = AgentScopeDeploymentAdapter()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_install_plans_classify_all_extension_types_and_paths(self) -> None:
        plans = {
            name: self.adapter.create_install_plan(package.archive, self.workspace)
            for name, package in self.packages.items()
        }

        self.assertEqual(plans["pdf-editor"].package.type.value, "skill")
        self.assertEqual(
            plans["pdf-editor"].mapping.relative_target,
            "skills/pdf-editor",
        )
        self.assertEqual(plans["wecom"].package.type.value, "plugin")
        self.assertEqual(
            plans["wecom"].mapping.relative_target,
            "extensions/plugins/wecom",
        )
        self.assertEqual(plans["telegram"].package.type.value, "adapter")
        self.assertEqual(
            plans["telegram"].mapping.relative_target,
            "extensions/adapters/telegram",
        )
        self.assertFalse(self.workspace.exists())

    def test_secret_validation_controls_install_readiness(self) -> None:
        package = self.packages["wecom"]
        blocked = self.adapter.create_install_plan(package.archive, self.workspace)
        ready = self.adapter.create_install_plan(
            package.archive,
            self.workspace,
            available_secrets=(
                "WECOM_BOT_ID",
                "WECOM_BOT_SECRET",
                "SN_API_KEY",
            ),
        )

        self.assertFalse(blocked.ready)
        self.assertEqual(
            blocked.secrets.missing,
            ("SN_API_KEY", "WECOM_BOT_ID", "WECOM_BOT_SECRET"),
        )
        self.assertTrue(ready.ready)
        self.assertEqual(ready.secrets.missing, ())

    def test_rollback_plan_targets_same_extension_and_previous_release(self) -> None:
        blocked = self.adapter.create_rollback_plan(
            self.current_package.archive,
            self.rollback_package.archive,
            self.workspace,
        )
        plan = self.adapter.create_rollback_plan(
            self.current_package.archive,
            self.rollback_package.archive,
            self.workspace,
            available_secrets=("ROLLBACK_TOKEN",),
        )

        self.assertFalse(blocked.ready)
        self.assertEqual(blocked.secrets.missing, ("ROLLBACK_TOKEN",))
        self.assertTrue(plan.ready)
        self.assertEqual(plan.current_package.version, "1.1.0")
        self.assertEqual(plan.rollback_package.version, "1.0.0")
        self.assertEqual(
            plan.mapping.relative_target,
            "extensions/plugins/rollback-fixture",
        )
        self.assertEqual(
            tuple(step.action for step in plan.steps),
            (
                RollbackAction.VERIFY_ROLLBACK_PACKAGE,
                RollbackAction.CHECK_SECRETS,
                RollbackAction.PRESERVE_CURRENT_TARGET,
                RollbackAction.RESTORE_PAYLOAD,
                RollbackAction.VERIFY_WORKSPACE,
            ),
        )
        self.assertFalse(plan.mapping.target_directory.exists())

        with self.assertRaisesRegex(
            AgentScopeDeploymentBridgeError,
            "one Extension identity",
        ):
            self.adapter.create_rollback_plan(
                self.current_package.archive,
                self.packages["telegram"].archive,
                self.workspace,
            )

    def test_install_report_contains_required_runtime_validation_fields(self) -> None:
        report_path = self.root / "reports" / "install-report.json"
        output = generate_install_report(
            (package.archive for package in self.packages.values()),
            self.workspace,
            report_path,
            available_secrets=(
                "WECOM_BOT_ID",
                "WECOM_BOT_SECRET",
                "SN_API_KEY",
                "TELEGRAM_BOT_TOKEN",
            ),
        )

        self.assertEqual(output, report_path.resolve())
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], INSTALL_REPORT_SCHEMA_VERSION)
        self.assertEqual(report["runtime_discovery"], RUNTIME_DISCOVERY_STATUS)
        self.assertTrue(report["all_ready"])
        self.assertEqual(
            [item["extension"] for item in report["extensions"]],
            ["pdf-editor", "telegram", "wecom"],
        )
        for record in report["extensions"]:
            self.assertEqual(
                set(record),
                {
                    "extension",
                    "type",
                    "version",
                    "target_path",
                    "required_secrets",
                    "missing_secrets",
                    "ready",
                    "plan_id",
                },
            )
            self.assertTrue(Path(record["target_path"]).is_relative_to(self.workspace))
            self.assertTrue(record["ready"])
        self.assertFalse(self.workspace.exists())

        with self.assertRaisesRegex(InstallReportError, "outside the target Workspace"):
            generate_install_report(
                (self.packages["pdf-editor"].archive,),
                self.workspace,
                self.workspace / "install-report.json",
            )

    @classmethod
    def _write_rollback_fixture(cls, version: str) -> None:
        cls.rollback_root.mkdir(parents=True)
        (cls.rollback_root / "README.md").write_text(
            "# Rollback fixture\n",
            encoding="utf-8",
        )
        (cls.rollback_root / "entrypoint.py").write_text(
            "def main():\n    return None\n",
            encoding="utf-8",
        )
        cls._write_rollback_manifest(version)

    @classmethod
    def _write_rollback_manifest(cls, version: str) -> None:
        manifest = {
            "name": "rollback-fixture",
            "type": "plugin",
            "version": version,
            "description": "Offline AgentScope rollback planning fixture.",
            "runtime": "python",
            "entrypoint": "entrypoint.py",
            "dependencies": [],
            "config_template": None,
            "healthcheck": None,
            "ports": [],
            "required_secrets": ["ROLLBACK_TOKEN"],
        }
        (cls.rollback_root / "manifest.yaml").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
