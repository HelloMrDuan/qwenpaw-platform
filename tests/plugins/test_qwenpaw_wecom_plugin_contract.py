from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from adapters.wecom.runtime import WeComRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent
from core.extensions import ExtensionRuntime, ExtensionType
from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
from tests.runtime._agentscope_flow_support import StaticRunningLifecycle


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_ROOT = REPOSITORY_ROOT / "plugins" / "runtime-wrapper"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wecom-channel-plugin"
WECOM_ROOT = REPOSITORY_ROOT / "plugins" / "wecom"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakePluginApi:
    def __init__(self) -> None:
        self.startup_hooks: list[tuple[str, object, int]] = []

    def register_startup_hook(self, name, callback, *, priority):
        self.startup_hooks.append((name, callback, priority))


class _FakeWeComTransport:
    def __init__(self) -> None:
        self.frames = [
            {
                "body": {
                    "msgid": "wecom-plugin-1001",
                    "chattype": "group",
                    "chatid": "wecom-group-1001",
                    "corpid": "corp-offline",
                    "from": {"userid": "wecom-user-1001", "name": "测试用户"},
                    "text": {"content": "WeCom Plugin 接收测试"},
                }
            },
            {
                "body": {
                    "msgid": "wecom-plugin-1002",
                    "chattype": "single",
                    "from": {"userid": "wecom-user-1002"},
                    "text": {"content": "WeCom MessageEvent 转发测试"},
                }
            },
        ]
        self.sent: list[tuple[str, str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline official Plugin wrapper for {descriptor.name}",
        )

    def receive_frame(self):
        return self.frames.pop(0) if self.frames else None

    def send_reply(self, target_id: str, text: str, reply_to: str) -> str:
        self.sent.append((target_id, text, reply_to))
        return "wecom-plugin-reply-1001"


class QwenPawWeComPluginContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(
            (PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8")
        )
        cls.template_module = _load_module(
            "qwenpaw_wecom_manifest_template_test",
            WRAPPER_ROOT / "manifest_template.py",
        )
        cls.plugin_module = _load_module(
            "wecom_official_qwenpaw_plugin_test",
            PLUGIN_ROOT / "plugin.py",
        )

    def test_plugin_json_matches_template_and_internal_manifest(self) -> None:
        document = self.document
        self.assertEqual(document["id"], "wecom-extension-channel")
        self.assertEqual(document["type"], "channel")
        self.assertEqual(document["entry"], {"backend": "plugin.py"})
        self.assertTrue((PLUGIN_ROOT / document["entry"]["backend"]).is_file())
        self.assertEqual(document["qwenpaw_version"], {"min": "2.1.0", "max": "2.2.0"})

        meta = document["meta"]
        self.assertEqual(meta["extension"]["name"], "wecom")
        self.assertEqual(meta["extension"]["type"], "plugin")
        self.assertEqual(meta["extension"]["runtime"], "node")
        self.assertEqual(
            meta["extension"]["adapter_entrypoint"],
            "adapters/wecom/runtime.py",
        )
        self.assertEqual(
            meta["required_secrets"],
            ["WECOM_BOT_ID", "WECOM_BOT_SECRET", "SN_API_KEY"],
        )
        self.assertEqual(meta["config"]["values"], {})
        self.assertEqual(
            [field["name"] for field in meta["config"]["fields"]],
            meta["required_secrets"],
        )
        self.assertTrue(
            all(field["secret"] is True for field in meta["config"]["fields"])
        )
        self.assertTrue(
            all("value" not in field for field in meta["config"]["fields"])
        )

        generated = self.template_module.build_plugin_manifest(
            WECOM_ROOT / "manifest.yaml",
            plugin_id="wecom-extension-channel",
            name="WeCom Extension Channel",
            description=(
                "Official QwenPaw Plugin facade for the recovered WeCom "
                "Extension Adapter."
            ),
            permissions=(
                "extension.registry.read",
                "extension.runtime.gateway",
                "channel.wecom.transport",
            ),
            config=meta["config"],
            plugin_type="channel",
            manifest_reference="plugins/wecom/manifest.yaml",
            adapter_entrypoint="adapters/wecom/runtime.py",
        )
        self.assertEqual(generated, document)

    def test_entry_delegates_to_existing_adapter_gateway_lifecycle_and_health(self) -> None:
        historical_files = (
            WECOM_ROOT / "recovered" / "wecom-node" / "wecom_bridge.mjs",
            WECOM_ROOT / "recovered" / "wecom-node" / "bot.mjs",
        )
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }
        plugin = self.plugin_module.WeComChannelPlugin()
        metadata = plugin.load_extension_manifest()
        self.assertEqual(metadata.name, "wecom")
        self.assertEqual(metadata.type, ExtensionType.PLUGIN)
        self.assertEqual(metadata.runtime, ExtensionRuntime.NODE)

        api = _FakePluginApi()
        plugin.register(api)
        self.assertEqual(len(api.startup_hooks), 1)
        hook_name, hook, priority = api.startup_hooks[0]
        self.assertEqual(hook_name, "wecom-extension-manifest")
        self.assertEqual(priority, 100)
        self.assertEqual(hook(), metadata)

        lifecycle = StaticRunningLifecycle(metadata)
        transport = _FakeWeComTransport()
        gateway = plugin.configure_runtime(
            lifecycle_manager=lifecycle,
            transport=transport,
        )
        self.assertIs(gateway.registry.get("wecom"), metadata)
        self.assertIsInstance(plugin.adapter, WeComRuntimeAdapter)

        message = plugin.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.channel.type, "wecom")
        self.assertEqual(message.session_id, "ses_wecom_wecom-group-1001")
        self.assertEqual(message.content.text, "WeCom Plugin 接收测试")
        self.assertEqual(
            plugin.forward_message_event(lambda event: event.content.text),
            "WeCom MessageEvent 转发测试",
        )

        receipt = plugin.send_response(message, "WeCom Plugin 回复测试")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "wecom-plugin-reply-1001")
        self.assertEqual(
            transport.sent,
            [("wecom-group-1001", "WeCom Plugin 回复测试", "wecom-plugin-1001")],
        )
        self.assertTrue(plugin.sync_lifecycle("health").healthy)
        self.assertEqual(
            {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in historical_files
            },
            hashes_before,
        )


if __name__ == "__main__":
    unittest.main()
