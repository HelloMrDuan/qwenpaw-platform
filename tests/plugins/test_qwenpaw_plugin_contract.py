from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from adapters.telegram.runtime import TelegramRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent
from core.extensions import ExtensionType
from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
from tests.runtime._agentscope_flow_support import StaticRunningLifecycle


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_ROOT = REPOSITORY_ROOT / "plugins" / "runtime-wrapper"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "telegram-channel-plugin"
TELEGRAM_ROOT = REPOSITORY_ROOT / "adapters" / "telegram"


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


class _FakeTelegramTransport:
    def __init__(self) -> None:
        self.updates = [
            {
                "update_id": 12001,
                "message": {
                    "message_id": 12002,
                    "date": 1_700_000_000,
                    "chat": {"id": 12003, "type": "private"},
                    "from": {"id": 12004, "first_name": "Plugin"},
                    "text": "官方 Plugin Wrapper 测试",
                },
            },
            {
                "update_id": 12006,
                "message": {
                    "message_id": 12007,
                    "date": 1_700_000_001,
                    "chat": {"id": 12003, "type": "private"},
                    "from": {"id": 12004, "first_name": "Plugin"},
                    "text": "MessageEvent 转发测试",
                },
            },
        ]
        self.sent: list[tuple[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline official Plugin wrapper for {descriptor.name}",
        )

    def receive_update(self):
        return self.updates.pop(0) if self.updates else None

    def send_message(self, chat_id: str, text: str) -> str:
        self.sent.append((chat_id, text))
        return "12005"


class QwenPawPluginContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(
            (PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8")
        )
        cls.template_module = _load_module(
            "qwenpaw_plugin_manifest_template_test",
            WRAPPER_ROOT / "manifest_template.py",
        )
        cls.plugin_module = _load_module(
            "telegram_official_qwenpaw_plugin_test",
            PLUGIN_ROOT / "plugin.py",
        )

    def test_plugin_json_matches_official_contract_and_generated_template(self) -> None:
        document = self.document
        self.assertEqual(
            set(document),
            {
                "id",
                "name",
                "version",
                "type",
                "description",
                "author",
                "entry",
                "dependencies",
                "qwenpaw_version",
                "meta",
            },
        )
        self.assertEqual(document["id"], "telegram-extension-channel")
        self.assertEqual(document["type"], "channel")
        self.assertEqual(document["version"], "0.1.0-recovered")
        self.assertEqual(document["entry"], {"backend": "plugin.py"})
        self.assertTrue((PLUGIN_ROOT / document["entry"]["backend"]).is_file())
        self.assertEqual(document["qwenpaw_version"], {"min": "2.1.0", "max": "2.2.0"})

        meta = document["meta"]
        self.assertEqual(meta["extension"]["name"], "telegram")
        self.assertEqual(meta["extension"]["type"], "adapter")
        self.assertEqual(
            meta["extension"]["adapter_entrypoint"],
            "adapters/telegram/runtime.py",
        )
        self.assertEqual(len(meta["permissions"]), len(set(meta["permissions"])))
        self.assertEqual(meta["config"]["values"], {})
        self.assertEqual(meta["required_secrets"], ["TELEGRAM_BOT_TOKEN"])
        self.assertNotIn("token", json.dumps(document).lower().replace("telegram_bot_token", ""))

        generated = self.template_module.build_plugin_manifest(
            TELEGRAM_ROOT / "manifest.yaml",
            plugin_id="telegram-extension-channel",
            name="Telegram Extension Channel",
            description=(
                "Official QwenPaw Plugin facade for the recovered Telegram "
                "Extension Adapter."
            ),
            permissions=(
                "extension.registry.read",
                "extension.runtime.gateway",
                "channel.telegram.transport",
            ),
            config=meta["config"],
            plugin_type="channel",
            manifest_reference="adapters/telegram/manifest.yaml",
            adapter_entrypoint="adapters/telegram/runtime.py",
        )
        self.assertEqual(generated, document)

    def test_plugin_entry_loads_registry_adapter_gateway_and_lifecycle(self) -> None:
        historical_files = (
            TELEGRAM_ROOT / "recovered" / "telegram_bridge.py",
            TELEGRAM_ROOT / "recovered" / "telegram_bridge_main.py",
        )
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }
        plugin = self.plugin_module.TelegramChannelPlugin()
        metadata = plugin.load_extension_manifest()
        self.assertEqual(metadata.name, "telegram")
        self.assertEqual(metadata.type, ExtensionType.ADAPTER)
        self.assertIs(plugin.runtime.registry.get("telegram"), metadata)

        api = _FakePluginApi()
        plugin.register(api)
        self.assertEqual(len(api.startup_hooks), 1)
        hook_name, hook, priority = api.startup_hooks[0]
        self.assertEqual(hook_name, "telegram-extension-manifest")
        self.assertEqual(priority, 100)
        self.assertEqual(hook(), metadata)

        lifecycle = StaticRunningLifecycle(metadata)
        transport = _FakeTelegramTransport()
        gateway = plugin.configure_runtime(
            lifecycle_manager=lifecycle,
            transport=transport,
        )
        self.assertIs(gateway.registry.get("telegram"), metadata)
        self.assertIsInstance(plugin.adapter, TelegramRuntimeAdapter)

        message = plugin.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.channel.type, "telegram")
        self.assertEqual(message.session_id, "ses_telegram_12003")
        self.assertEqual(message.content.text, "官方 Plugin Wrapper 测试")
        forwarded = plugin.forward_message_event(lambda event: event.content.text)
        self.assertEqual(forwarded, "MessageEvent 转发测试")

        receipt = plugin.send_response(message, "官方 Plugin Wrapper 回复")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "12005")
        self.assertEqual(transport.sent, [("12003", "官方 Plugin Wrapper 回复")])
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
