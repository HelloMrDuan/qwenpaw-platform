import json
import unittest
from pathlib import Path

from core.extensions import (
    ExtensionLoader,
    ExtensionRegistry,
    ExtensionRuntime,
    ExtensionType,
    ManifestValidationError,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "pdf-editor"
MANIFEST_PATH = SKILL_ROOT / "manifest.yaml"


class SkillExtensionRegistryTests(unittest.TestCase):
    def test_pdf_editor_is_discovered_as_skill_not_plugin(self) -> None:
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.discover()

        metadata = registry.get("pdf-editor")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.type, ExtensionType.SKILL)
        self.assertEqual(metadata.runtime, ExtensionRuntime.PYTHON)
        self.assertEqual(metadata.version, "1.2.0")
        self.assertNotIn(metadata, registry.list(ExtensionType.PLUGIN))
        self.assertIn(metadata, registry.list(ExtensionType.SKILL))

    def test_executor_and_schema_paths_are_validated_and_preserved(self) -> None:
        metadata = ExtensionLoader().load_metadata(
            MANIFEST_PATH,
            expected_type=ExtensionType.SKILL,
        )

        self.assertEqual(metadata.entrypoint, "executor/main.py")
        self.assertEqual(metadata.executor["callable"], "execute")
        self.assertTrue((SKILL_ROOT / metadata.entrypoint).is_file())
        self.assertEqual(set(metadata.schemas), {"request", "result"})
        for schema_path in metadata.schemas.values():
            self.assertTrue((SKILL_ROOT / schema_path).is_file())

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        invalid = dict(manifest)
        invalid["schemas"] = dict(manifest["schemas"])
        invalid["schemas"]["request"] = "schemas/missing.schema.json"
        with self.assertRaisesRegex(ManifestValidationError, "schemas.request"):
            ExtensionLoader().validate_manifest(
                invalid,
                manifest_path=MANIFEST_PATH,
                expected_type=ExtensionType.SKILL,
            )

    def test_artifact_and_event_declarations_match_contract_boundary(self) -> None:
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.discover()
        metadata = registry.get("pdf-editor")

        self.assertEqual(metadata.artifacts["uri_scheme"], "artifact")
        self.assertEqual(
            metadata.artifacts["outputs"],
            [
                {
                    "name": "edited_pdf",
                    "kind": "file",
                    "mime_types": ["application/pdf"],
                    "required": True,
                }
            ],
        )
        self.assertEqual(
            set(metadata.events),
            {
                "tool.start",
                "tool.progress",
                "file.created",
                "tool.result",
                "tool.error",
            },
        )

    def test_legacy_skill_descriptor_remains_alongside_extension_manifest(self) -> None:
        self.assertTrue((SKILL_ROOT / "skill.yaml").is_file())
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertNotEqual(
            (SKILL_ROOT / "skill.yaml").read_text(encoding="utf-8"),
            MANIFEST_PATH.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
