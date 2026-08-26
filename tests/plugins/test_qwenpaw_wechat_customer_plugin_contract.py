from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from adapters.wechat_customer.runtime import WeChatCustomerRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent
from core.extensions import ExtensionRuntime, ExtensionType
from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
from tests._qwenpaw_v2_1_support import install_qwenpaw_v2_1_stubs
from tests.runtime._agentscope_flow_support import StaticRunningLifecycle


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_ROOT = REPOSITORY_ROOT / "plugins" / "runtime-wrapper"
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer-channel-plugin"
GATEWAY_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer"
HISTORICAL_GATEWAY = GATEWAY_ROOT / "recovered" / "wecom_kf_gateway_v345.py"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _gateway_event(message_id: str, content: str) -> dict[str, object]:
    return {
        "msgid": message_id,
        "msgtype": "text",
        "origin": 3,
        "external_userid": "wm-plugin-customer-001",
        "open_kfid": "wk-plugin-service-001",
        "text": {"content": content},
        "gateway_delivery": {
            "delivery_id": f"gateway-{message_id}",
            "cursor_committed": True,
            "db_claimed": True,
        },
    }


class _FakePluginApi:
    def __init__(self) -> None:
        self.channels: list[dict[str, object]] = []

    def register_channel(self, **kwargs):
        self.channels.append(kwargs)


class _FakeWeChatCustomerTransport:
    def __init__(self) -> None:
        self.events = [
            _gateway_event("wechat-plugin-1001", "微信客服 Plugin 接收测试"),
            _gateway_event("wechat-plugin-1002", "微信客服 MessageEvent 转发测试"),
        ]
        self.sent: list[tuple[str, str, str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline official Plugin wrapper for {descriptor.name}",
        )

    def receive_event(self):
        return self.events.pop(0) if self.events else None

    def send_text(
        self,
        external_userid: str,
        open_kfid: str,
        text: str,
        reply_to: str,
    ) -> str:
        self.sent.append((external_userid, open_kfid, text, reply_to))
        return "wechat-plugin-reply-1001"


class QwenPawWeChatCustomerPluginContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_channel = install_qwenpaw_v2_1_stubs()
        cls.document = json.loads(
            (PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8")
        )
        cls.template_module = _load_module(
            "qwenpaw_wechat_customer_manifest_template_test",
            WRAPPER_ROOT / "manifest_template.py",
        )
        cls.plugin_module = _load_module(
            "wechat_customer_official_qwenpaw_plugin_test",
            PLUGIN_ROOT / "plugin.py",
        )

    def test_plugin_json_matches_template_and_internal_manifest(self) -> None:
        document = self.document
        self.assertEqual(document["id"], "wechat-customer-extension-channel")
        self.assertEqual(document["type"], "channel")
        self.assertEqual(document["entry"], {"backend": "plugin.py"})
        self.assertTrue((PLUGIN_ROOT / document["entry"]["backend"]).is_file())
        self.assertEqual(document["qwenpaw_version"], {"min": "2.1.0", "max": "2.2.0"})

        meta = document["meta"]
        self.assertEqual(meta["extension"]["name"], "wechat-customer")
        self.assertEqual(meta["extension"]["type"], "plugin")
        self.assertEqual(meta["extension"]["runtime"], "python")
        self.assertEqual(
            meta["extension"]["adapter_entrypoint"],
            "adapters/wechat_customer/runtime.py",
        )
        self.assertEqual(
            meta["required_secrets"],
            ["app_secret", "callback_token", "encoding_aes_key"],
        )
        self.assertEqual(meta["config"]["values"], {})
        self.assertEqual(
            [field["name"] for field in meta["config"]["fields"]],
            [
                "corp_id",
                "app_secret",
                "callback_token",
                "encoding_aes_key",
                "open_kfid",
                "gateway_url",
            ],
        )
        self.assertEqual(
            [
                field["name"]
                for field in meta["config"]["fields"]
                if field["secret"] is True
            ],
            meta["required_secrets"],
        )
        self.assertTrue(
            all("value" not in field for field in meta["config"]["fields"])
        )

        generated = self.template_module.build_plugin_manifest(
            GATEWAY_ROOT / "manifest.yaml",
            plugin_id="wechat-customer-extension-channel",
            name="WeChat Customer Extension Channel",
            description=(
                "Native QwenPaw Channel wrapper for the external recovered "
                "WeChat Customer Gateway."
            ),
            permissions=(
                "extension.registry.read",
                "extension.runtime.gateway",
                "channel.wechat-customer.transport",
            ),
            config=meta["config"],
            plugin_type="channel",
            manifest_reference="plugins/wechat-customer/manifest.yaml",
            adapter_entrypoint="adapters/wechat_customer/runtime.py",
            config_mapping=meta["extension"]["config_mapping"],
        )
        self.assertEqual(generated, document)

    def test_entry_preserves_gateway_state_ownership_and_delegates_runtime(self) -> None:
        source_hash = hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest()
        state_files_before = self._gateway_state_files()
        plugin = self.plugin_module.WeChatCustomerChannelPlugin()
        metadata = plugin.load_extension_manifest()
        self.assertEqual(metadata.name, "wechat-customer")
        self.assertEqual(metadata.type, ExtensionType.PLUGIN)
        self.assertEqual(metadata.runtime, ExtensionRuntime.PYTHON)

        api = _FakePluginApi()
        plugin.register(api)
        self.assertEqual(len(api.channels), 1)
        registration = api.channels[0]
        channel_class = registration["channel_class"]
        self.assertTrue(issubclass(channel_class, self.base_channel))
        self.assertEqual(channel_class.channel, "wechat_customer")

        lifecycle = StaticRunningLifecycle(metadata)
        transport = _FakeWeChatCustomerTransport()
        gateway = plugin.configure_runtime(
            lifecycle_manager=lifecycle,
            transport=transport,
        )
        self.assertIs(gateway.registry.get("wechat-customer"), metadata)
        self.assertIsInstance(plugin.adapter, WeChatCustomerRuntimeAdapter)

        message = plugin.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.channel.type, "wechat-customer")
        self.assertEqual(message.content.text, "微信客服 Plugin 接收测试")
        self.assertTrue(message.metadata["cursor_committed"])
        self.assertTrue(message.metadata["db_claimed"])
        self.assertEqual(message.metadata["state_owner"], "gateway")
        self.assertEqual(
            plugin.forward_message_event(lambda event: event.content.text),
            "微信客服 MessageEvent 转发测试",
        )

        receipt = plugin.send_response(message, "微信客服 Plugin 回复测试")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "wechat-plugin-reply-1001")
        self.assertEqual(receipt.metadata["state_owner"], "gateway")
        self.assertEqual(
            transport.sent,
            [
                (
                    "wm-plugin-customer-001",
                    "wk-plugin-service-001",
                    "微信客服 Plugin 回复测试",
                    "wechat-plugin-1001",
                )
            ],
        )
        self.assertTrue(plugin.sync_lifecycle("health").healthy)
        self.assertEqual(
            hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest(),
            source_hash,
        )
        self.assertEqual(self._gateway_state_files(), state_files_before)

    @staticmethod
    def _gateway_state_files() -> tuple[str, ...]:
        patterns = ("*.db", "*.db-*", "*cursor*.json", "*cursor*.tmp")
        return tuple(
            sorted(
                str(path.relative_to(GATEWAY_ROOT))
                for pattern in patterns
                for path in GATEWAY_ROOT.rglob(pattern)
                if path.is_file()
            )
        )


if __name__ == "__main__":
    unittest.main()
