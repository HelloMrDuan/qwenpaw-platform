from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPOSITORY_ROOT / "plugins" / "sensenova-image-generation-tool" / "sensenova_image_generation.py"


class _Block:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _ToolChunk:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def _load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _agentscope_stubs(include_middleware: bool = False) -> dict[str, ModuleType]:
    root = ModuleType("agentscope")
    message = ModuleType("agentscope.message")
    message.DataBlock = _Block
    message.TextBlock = _Block
    message.URLSource = _Block
    message.ToolResultState = SimpleNamespace(SUCCESS="SUCCESS", ERROR="ERROR")
    tool = ModuleType("agentscope.tool")
    tool.ToolChunk = _ToolChunk
    result = {"agentscope": root, "agentscope.message": message, "agentscope.tool": tool}
    if include_middleware:
        middleware = ModuleType("agentscope.middleware")
        middleware.MiddlewareBase = object
        result["agentscope.middleware"] = middleware
    return result


def _success(path: Path) -> dict:
    return {
        "status": "SUCCESS",
        "images": [{"path": str(path), "mime_type": "image/png"}],
        "artifacts": [
            {
                "id": "sha256:test",
                "name": path.name,
                "mime_type": "image/png",
                "uri": "artifact://result.png",
                "sha256": "a" * 64,
            }
        ],
        "provider": "sensenova",
        "model": "sensenova-u1-fast",
        "requested_size": "1920x1080",
        "requested_aspect_ratio": "16:9",
        "image_size": "2k",
        "provider_size": "2752x1536",
        "provider_aspect_ratio": "16:9",
        "final_size": "1920x1080",
        "retryable": False,
        "metadata": {"tool_call_id": "call-1", "request_id": "turn-1"},
    }


class ImageGenerationTerminalTests(unittest.TestCase):
    def test_11_schema_removes_arbitrary_width_height(self) -> None:
        module = _load_tool("sensenova_terminal_schema")
        parameters = inspect.signature(module.image_generation).parameters
        self.assertNotIn("width", parameters)
        self.assertNotIn("height", parameters)
        self.assertIn("aspect_ratio", parameters)
        self.assertIn("image_size", parameters)

    def test_12_schema_uses_literal_size_and_ratio_types(self) -> None:
        module = _load_tool("sensenova_terminal_literals")
        self.assertEqual(module.ImageSize.__args__, ("1k", "2k"))
        self.assertIn("16:9", module.AspectRatio.__args__)
        self.assertNotIn("21:9", module.AspectRatio.__args__)

    def test_13_success_is_terminal_tool_chunk(self) -> None:
        module = _load_tool("sensenova_terminal_success")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        self.assertEqual(chunk.state, "SUCCESS")

    def test_14_success_contains_image_data_block(self) -> None:
        module = _load_tool("sensenova_terminal_data")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        self.assertTrue(any(hasattr(item, "source") for item in chunk.content))

    def test_15_success_summary_is_completed_without_error(self) -> None:
        module = _load_tool("sensenova_terminal_json")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        summary = json.loads(chunk.content[-1].text)
        self.assertEqual(summary["status"], "completed")
        self.assertTrue(summary["success"])
        self.assertNotIn("error", summary)

    def test_16_failure_is_error_tool_chunk(self) -> None:
        module = _load_tool("sensenova_terminal_failure")
        failed = {
            "status": "FAILED",
            "error": "bad request",
            "error_code": "INVALID_ARGUMENT",
            "retryable": False,
            "metadata": {},
        }
        with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
            module, "invoke_image_generation_tool", return_value=failed
        ):
            chunk = asyncio.run(module.image_generation("draw"))
        self.assertEqual(chunk.state, "ERROR")

    def test_17_failure_never_contains_image_data(self) -> None:
        module = _load_tool("sensenova_terminal_no_data")
        failed = {
            "status": "FAILED",
            "error": "bad request",
            "error_code": "INVALID_ARGUMENT",
            "retryable": False,
            "metadata": {},
        }
        with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
            module, "invoke_image_generation_tool", return_value=failed
        ):
            chunk = asyncio.run(module.image_generation("draw"))
        self.assertFalse(any(hasattr(item, "source") for item in chunk.content))

    def test_18_middleware_captures_tool_call_and_user_turn(self) -> None:
        module = _load_tool("sensenova_terminal_middleware")
        with patch.dict(sys.modules, _agentscope_stubs(include_middleware=True)):
            middleware = module.image_generation_middleware_factory(None, None)
            user = SimpleNamespace(role="user", id="turn-77", metadata={})
            agent = SimpleNamespace(
                state=SimpleNamespace(context=[user]), _request_context={}
            )
            tool_call = SimpleNamespace(name="image_generation", id="call-88")

            async def next_handler():
                yield (module._TOOL_CALL_ID.get(), module._REQUEST_ID.get())

            async def consume():
                return [
                    item
                    async for item in middleware.on_acting(
                        agent, {"tool_call": tool_call}, next_handler
                    )
                ]

            values = asyncio.run(consume())
        self.assertEqual(values, [("call-88", "turn-77")])

    def test_29_image_content_part_preserves_mime(self) -> None:
        module = _load_tool("sensenova_terminal_mime")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        data = next(item for item in chunk.content if hasattr(item, "source"))
        self.assertEqual(data.source.media_type, "image/png")

    def test_30_artifact_uri_is_preserved_in_terminal_summary(self) -> None:
        module = _load_tool("sensenova_terminal_uri")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        summary = json.loads(chunk.content[-1].text)
        self.assertEqual(summary["artifacts"][0]["uri"], "artifact://result.png")

    def test_31_artifact_checksum_is_preserved_in_terminal_summary(self) -> None:
        module = _load_tool("sensenova_terminal_checksum")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        summary = json.loads(chunk.content[-1].text)
        self.assertEqual(summary["artifacts"][0]["sha256"], "a" * 64)

    def test_32_prior_failure_fields_do_not_contaminate_success(self) -> None:
        module = _load_tool("sensenova_terminal_clean_success")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            success = _success(image)
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module,
                "invoke_image_generation_tool",
                side_effect=[
                    {
                        "status": "FAILED",
                        "error": "unsupported size",
                        "error_code": "UNSUPPORTED_NATIVE_SIZE",
                        "retryable": False,
                        "metadata": {},
                    },
                    success,
                ],
            ):
                asyncio.run(module.image_generation("bad"))
                chunk = asyncio.run(module.image_generation("good"))
        summary = json.loads(chunk.content[-1].text)
        self.assertNotIn("error", summary)
        self.assertNotIn("unsupported", json.dumps(summary).lower())

    def test_33_official_contract_is_success_data_plus_text(self) -> None:
        module = _load_tool("sensenova_terminal_contract")
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "result.png"
            image.write_bytes(b"image")
            with patch.dict(sys.modules, _agentscope_stubs()), patch.object(
                module, "invoke_image_generation_tool", return_value=_success(image)
            ):
                chunk = asyncio.run(module.image_generation("draw"))
        self.assertEqual(chunk.state, "SUCCESS")
        self.assertTrue(hasattr(chunk.content[0], "source"))
        self.assertTrue(hasattr(chunk.content[-1], "text"))


if __name__ == "__main__":
    unittest.main()
