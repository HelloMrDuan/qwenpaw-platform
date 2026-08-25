from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from core.deployment import (
    AgentScopeDeploymentAdapter,
    AgentScopeDeploymentBridgeError,
    InstallAction,
    WorkspaceMapper,
)
from core.extensions import ExtensionType
from scripts.build_extension import build_extension, sha256_file


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class AgentScopeDeploymentBridgeTests(unittest.TestCase):
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
        cls.adapter = AgentScopeDeploymentAdapter()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_package_parser_reuses_integrity_and_manifest_validation(self) -> None:
        package = self.packages["pdf-editor"]
        descriptor = self.adapter.parse_package(
            package.archive,
            expected_sha256=package.sha256,
        )

        self.assertEqual(descriptor.name, "pdf-editor")
        self.assertEqual(descriptor.type, ExtensionType.SKILL)
        self.assertEqual(descriptor.version, "1.2.0")
        self.assertEqual(descriptor.sha256, sha256_file(package.archive))
        self.assertIn("manifest.yaml", descriptor.files)
        self.assertIn("executor/main.py", descriptor.files)
        self.assertEqual(descriptor.required_secrets, ())

        invalid = self.root / "invalid-manifest.skill.zip"
        with zipfile.ZipFile(package.archive) as source, zipfile.ZipFile(
            invalid, "w"
        ) as destination:
            for info in source.infolist():
                content = source.read(info)
                if info.filename == "manifest.yaml":
                    manifest = json.loads(content.decode("utf-8"))
                    manifest.pop("executor")
                    content = json.dumps(manifest).encode("utf-8")
                destination.writestr(info, content)
        invalid.with_suffix(".zip.sha256").write_text(
            f"{sha256_file(invalid)}  {invalid.name}\n",
            encoding="utf-8",
        )
        with self.assertRaises(AgentScopeDeploymentBridgeError):
            self.adapter.parse_package(invalid)

    def test_workspace_mapper_generates_type_specific_targets_without_writes(self) -> None:
        descriptors = tuple(
            self.adapter.parse_package(package.archive)
            for package in self.packages.values()
        )
        mappings = WorkspaceMapper().map_packages(descriptors, self.workspace)
        by_name = {mapping.extension_name: mapping for mapping in mappings}

        self.assertEqual(by_name["pdf-editor"].relative_target, "skills/pdf-editor")
        self.assertEqual(
            by_name["wecom"].relative_target,
            "extensions/plugins/wecom",
        )
        self.assertEqual(
            by_name["telegram"].relative_target,
            "extensions/adapters/telegram",
        )
        for mapping in mappings:
            self.assertTrue(mapping.target_directory.is_relative_to(self.workspace))
            self.assertFalse(mapping.target_directory.exists())
        self.assertFalse(self.workspace.exists())

    def test_install_plan_is_deterministic_and_contains_no_execution(self) -> None:
        package = self.packages["pdf-editor"]
        first = self.adapter.create_install_plan(
            package.archive,
            self.workspace,
            expected_sha256=package.sha256,
        )
        second = self.adapter.create_install_plan(
            package.archive,
            self.workspace,
            expected_sha256=package.sha256,
        )

        self.assertTrue(first.ready)
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertEqual(first.mapping.relative_target, "skills/pdf-editor")
        self.assertEqual(
            tuple(step.order for step in first.steps),
            (1, 2, 3, 4, 5),
        )
        self.assertEqual(
            tuple(step.action for step in first.steps),
            (
                InstallAction.VERIFY_PACKAGE,
                InstallAction.CHECK_SECRETS,
                InstallAction.PREPARE_TARGET,
                InstallAction.INSTALL_PAYLOAD,
                InstallAction.VERIFY_WORKSPACE,
            ),
        )
        self.assertFalse(first.mapping.target_directory.exists())
        serialized = first.to_dict()
        self.assertEqual(serialized["ready"], True)
        self.assertEqual(serialized["package"]["sha256"], package.sha256)

    def test_secret_check_reports_names_only_and_blocks_incomplete_plan(self) -> None:
        package = self.packages["wecom"]
        descriptor = self.adapter.parse_package(package.archive)
        self.assertEqual(
            descriptor.required_secrets,
            ("SN_API_KEY", "WECOM_BOT_ID", "WECOM_BOT_SECRET"),
        )

        incomplete = self.adapter.create_install_plan(
            package.archive,
            self.workspace,
            available_secrets=("WECOM_BOT_ID",),
        )
        self.assertFalse(incomplete.ready)
        self.assertEqual(incomplete.secrets.available, ("WECOM_BOT_ID",))
        self.assertEqual(
            incomplete.secrets.missing,
            ("SN_API_KEY", "WECOM_BOT_SECRET"),
        )

        complete = self.adapter.create_install_plan(
            package.archive,
            self.workspace,
            available_secrets=descriptor.required_secrets,
        )
        self.assertTrue(complete.ready)
        self.assertEqual(complete.secrets.missing, ())
        self.assertNotIn("secret-value", json.dumps(complete.to_dict()))

        with self.assertRaisesRegex(TypeError, "names only"):
            self.adapter.create_install_plan(
                package.archive,
                self.workspace,
                available_secrets={"WECOM_BOT_ID": "secret-value"},
            )


if __name__ == "__main__":
    unittest.main()
