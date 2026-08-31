import importlib.util
import inspect
from pathlib import Path
import sys
import typing
import unittest

from pydantic import TypeAdapter, create_model


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = (
    REPOSITORY_ROOT
    / "plugins"
    / "sensenova-image-generation-tool"
    / "sensenova_image_generation.py"
)


def _load_tool():
    name = "sensenova_qwenpaw_schema_regression"
    spec = importlib.util.spec_from_file_location(name, TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _dynamic_input_model(function):
    """Mirror QwenPaw's signature-driven Pydantic v2 model construction."""

    fields = {}
    for name, parameter in inspect.signature(function).parameters.items():
        default = (
            ...
            if parameter.default is inspect.Parameter.empty
            else parameter.default
        )
        fields[name] = (parameter.annotation, default)
    return create_model("StructuredOutputDynamicClass", **fields)


class QwenPawToolSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_tool()
        cls.function = cls.module.image_generation
        cls.signature = inspect.signature(cls.function)
        cls.hints = typing.get_type_hints(cls.function)
        cls.model = _dynamic_input_model(cls.function)

    def test_01_signature_contains_no_string_annotations(self) -> None:
        self.assertFalse(
            any(
                isinstance(parameter.annotation, str)
                for parameter in self.signature.parameters.values()
            )
        )

    def test_02_get_type_hints_has_no_forward_refs(self) -> None:
        self.assertFalse(
            any(isinstance(value, typing.ForwardRef) for value in self.hints.values())
        )

    def test_03_type_adapter_accepts_public_parameter_types(self) -> None:
        TypeAdapter(self.hints["aspect_ratio"]).validate_python("16:9")
        TypeAdapter(self.hints["image_size"]).validate_python("2k")
        TypeAdapter(self.hints["fit_mode"]).validate_python("cover")

    def test_04_create_model_is_fully_defined(self) -> None:
        self.assertTrue(self.model.__pydantic_complete__)

    def test_05_json_schema_generation_succeeds(self) -> None:
        schema = self.model.model_json_schema()
        self.assertIn("aspect_ratio", schema["properties"])
        self.assertIn("image_size", schema["properties"])

    def test_06_model_rebuild_needs_no_external_namespace(self) -> None:
        self.model.model_rebuild(force=True)
        self.assertTrue(self.model.__pydantic_complete__)

    def test_07_aspect_ratio_enum_matches_official_contract(self) -> None:
        schema = self.model.model_json_schema()["properties"]["aspect_ratio"]
        enum_values = schema["anyOf"][0]["enum"]
        self.assertEqual(enum_values, list(self.module.AspectRatio.__args__))

    def test_08_image_size_enum_is_1k_and_2k(self) -> None:
        schema = self.model.model_json_schema()["properties"]["image_size"]
        self.assertEqual(schema["enum"], ["1k", "2k"])

    def test_09_default_parameters_are_preserved(self) -> None:
        instance = self.model(prompt="draw")
        self.assertIsNone(instance.aspect_ratio)
        self.assertEqual(instance.image_size, "2k")
        self.assertIsNone(instance.fit_mode)

    def test_10_aspect_ratio_can_be_omitted(self) -> None:
        self.assertIsNone(self.model(prompt="draw").aspect_ratio)

    def test_11_aspect_ratio_accepts_1_to_1(self) -> None:
        self.assertEqual(
            self.model(prompt="draw", aspect_ratio="1:1").aspect_ratio,
            "1:1",
        )

    def test_12_aspect_ratio_accepts_16_to_9(self) -> None:
        self.assertEqual(
            self.model(prompt="draw", aspect_ratio="16:9").aspect_ratio,
            "16:9",
        )

    def test_13_aspect_ratio_accepts_9_to_16(self) -> None:
        self.assertEqual(
            self.model(prompt="draw", aspect_ratio="9:16").aspect_ratio,
            "9:16",
        )


if __name__ == "__main__":
    unittest.main()
