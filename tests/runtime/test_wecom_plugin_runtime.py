from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.wecom.runtime import WeComRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent, MessageType
from core.extensions import ExtensionRegistry, ExtensionRuntime, ExtensionType
from core.extensions.lifecycle import ExtensionLifecycleManager, ExtensionState
from core.extensions.runtime import (
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
)
from scripts.build_extension import build_extension


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WECOM_ROOT = REPOSITORY_ROOT / "plugins" / "wecom"


class _FakeWeComTransport:
    def __init__(self) -> None:
        self.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail="fake recovered WeCom process is reachable",
        )
        self.frames = [
            {
                "body": {
                    "msgid": "wecom-msg-1001",
                    "chattype": "group",
                    "chatid": "group-8001",
                    "corpid": "corp-test",
                    "from": {
                        "userid": "zhangsan",
                        "name": "张三",
                    },
                    "text": {"content": "请处理这条企业微信测试消息"},
                }
            }
        ]
        self.sent: list[tuple[str, str, str]] = []
        self.probed_entrypoints: list[Path] = []

    def check(self, descriptor):
        self.probed_entrypoints.append(descriptor.entrypoint_path)
        return self.snapshot

    def receive_frame(self):
        return self.frames.pop(0) if self.frames else None

    def send_reply(self, target_id: str, text: str, reply_to: str) -> str:
        self.sent.append((target_id, text, reply_to))
        return "wecom-reply-9001"


class WeComPluginRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.package_output = self.root / "dist"
        self.deployments = self.root / "workspace" / "extensions"
        self.registry = ExtensionRegistry(REPOSITORY_ROOT)
        self.discovered = self.registry.discover()
        self.package = build_extension(WECOM_ROOT / "manifest.yaml", self.package_output)
        self.lifecycle = ExtensionLifecycleManager(self.deployments)
        self.lifecycle.install(self.package.archive)
        self.transport = _FakeWeComTransport()
        self.plugin_bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT,
            self.registry,
            self.lifecycle,
            probe=self.transport,
        )
        self.adapter = WeComRuntimeAdapter(
            self.plugin_bridge,
            self.transport,
            instance_id="wecom-runtime-test",
            clock=lambda: datetime(2026, 8, 25, 8, 0, 0, tzinfo=timezone.utc),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_plugin_discovery_lifecycle_message_and_delivery_round_trip(self) -> None:
        historical_files = [
            WECOM_ROOT / "recovered" / "wecom-node" / "wecom_bridge.mjs",
            WECOM_ROOT / "recovered" / "wecom-node" / "bot.mjs",
        ]
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }

        metadata = self.registry.get("wecom")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertIn(metadata, self.discovered)
        self.assertEqual(metadata.type, ExtensionType.PLUGIN)
        self.assertEqual(metadata.runtime, ExtensionRuntime.NODE)
        self.assertEqual(
            metadata.entrypoint,
            "recovered/wecom-node/wecom_bridge.mjs",
        )
        descriptor = self.plugin_bridge.describe("wecom")
        self.assertEqual(descriptor.name, "wecom")
        self.assertEqual(
            descriptor.entrypoint_path,
            WECOM_ROOT / "recovered" / "wecom-node" / "wecom_bridge.mjs",
        )

        health = self.adapter.health_check()
        self.assertTrue(health.healthy)
        self.assertTrue(health.deployment_verified)
        self.assertTrue(health.runtime_probe_performed)
        self.assertEqual(health.code, "SERVICE_RUNNING")
        self.assertEqual(health.state, ExtensionState.RUNNING)
        self.assertEqual(self.lifecycle.get("wecom").state, ExtensionState.RUNNING)
        self.assertEqual(
            self.transport.probed_entrypoints,
            [descriptor.entrypoint_path],
        )

        message = self.adapter.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.type, MessageType.TEXT)
        self.assertEqual(message.channel.type, "wecom")
        self.assertEqual(message.channel.message_id, "wecom-msg-1001")
        self.assertEqual(message.channel.thread_id, "group-8001")
        self.assertEqual(message.channel.tenant_id, "corp-test")
        self.assertEqual(message.user.external_id, "zhangsan")
        self.assertEqual(message.user.display_name, "张三")
        self.assertEqual(message.session_id, "ses_wecom_group-8001")
        self.assertEqual(message.timestamp, "2026-08-25T08:00:00Z")
        self.assertEqual(message.content.text, "请处理这条企业微信测试消息")
        self.assertEqual(message.metadata["target_id"], "group-8001")
        self.assertEqual(message.metadata["timestamp_source"], "extension_received_at")

        receipt = self.adapter.send_response(message, "这是企业微信桥接层测试回复")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "wecom-reply-9001")
        self.assertEqual(
            self.transport.sent,
            [
                (
                    "group-8001",
                    "这是企业微信桥接层测试回复",
                    "wecom-msg-1001",
                )
            ],
        )
        self.assertIsNone(self.adapter.receive_message())

        self.transport.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.STOPPED,
            reachable=False,
            detail="fake recovered WeCom process stopped",
        )
        stopped = self.adapter.health_check()
        self.assertFalse(stopped.healthy)
        self.assertEqual(stopped.code, "SERVICE_STOPPED")
        self.assertEqual(stopped.state, ExtensionState.ENABLED)
        self.assertEqual(self.lifecycle.get("wecom").state, ExtensionState.ENABLED)

        hashes_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }
        self.assertEqual(hashes_after, hashes_before)

    def test_direct_message_uses_sender_as_target_and_body_content_fallback(self) -> None:
        message = self.adapter.parse_message(
            {
                "body": {
                    "msgid": "wecom-msg-1002",
                    "chattype": "single",
                    "from": {"userid": "lisi"},
                    "content": "备用历史消息结构",
                }
            }
        )

        self.assertEqual(message.channel.thread_id, "lisi")
        self.assertEqual(message.content.text, "备用历史消息结构")
        self.assertEqual(message.metadata["target_id"], "lisi")


if __name__ == "__main__":
    unittest.main()
