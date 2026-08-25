from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.telegram.runtime import TelegramRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent, MessageType
from core.extensions import ExtensionRegistry, ExtensionType
from core.extensions.lifecycle import ExtensionLifecycleManager, ExtensionState
from core.extensions.runtime import (
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
)
from scripts.build_extension import build_extension


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_ROOT = REPOSITORY_ROOT / "adapters" / "telegram"


class _FakeTelegramTransport:
    def __init__(self) -> None:
        self.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail="fake recovered Telegram process is reachable",
        )
        self.updates = [
            {
                "update_id": 7001,
                "message": {
                    "message_id": 81,
                    "date": 1_700_000_000,
                    "from": {
                        "id": 10001,
                        "first_name": "Test",
                        "last_name": "User",
                        "username": "test_user",
                    },
                    "chat": {"id": -90001, "type": "group"},
                    "text": "请处理这条Telegram测试消息",
                },
            }
        ]
        self.sent: list[tuple[str, str]] = []
        self.probed_entrypoints: list[Path] = []

    def check(self, descriptor):
        self.probed_entrypoints.append(descriptor.entrypoint_path)
        return self.snapshot

    def receive_update(self):
        return self.updates.pop(0) if self.updates else None

    def send_message(self, chat_id: str, text: str) -> str:
        self.sent.append((chat_id, text))
        return "9001"


class TelegramPluginRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.package_output = self.root / "dist"
        self.deployments = self.root / "workspace" / "extensions"
        self.registry = ExtensionRegistry(REPOSITORY_ROOT)
        self.discovered = self.registry.discover()
        self.package = build_extension(
            TELEGRAM_ROOT / "manifest.yaml", self.package_output
        )
        self.lifecycle = ExtensionLifecycleManager(self.deployments)
        self.lifecycle.install(self.package.archive)
        self.transport = _FakeTelegramTransport()
        self.plugin_bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT,
            self.registry,
            self.lifecycle,
            probe=self.transport,
        )
        self.adapter = TelegramRuntimeAdapter(
            self.plugin_bridge,
            self.transport,
            instance_id="telegram-runtime-test",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_discovery_health_message_conversion_and_response_round_trip(self) -> None:
        historical_files = [
            TELEGRAM_ROOT / "recovered" / "telegram_bridge.py",
            TELEGRAM_ROOT / "recovered" / "telegram_bridge_main.py",
        ]
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }

        metadata = self.registry.get("telegram")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertIn(metadata, self.discovered)
        self.assertEqual(metadata.type, ExtensionType.ADAPTER)
        self.assertEqual(
            metadata.entrypoint, "recovered/telegram_bridge_main.py"
        )
        descriptor = self.plugin_bridge.describe("telegram")
        self.assertEqual(descriptor.name, "telegram")
        self.assertEqual(
            descriptor.entrypoint_path,
            TELEGRAM_ROOT / "recovered" / "telegram_bridge_main.py",
        )

        health = self.adapter.health_check()
        self.assertTrue(health.healthy)
        self.assertTrue(health.deployment_verified)
        self.assertTrue(health.runtime_probe_performed)
        self.assertEqual(health.code, "SERVICE_RUNNING")
        self.assertEqual(health.state, ExtensionState.RUNNING)
        self.assertEqual(
            self.lifecycle.get("telegram").state, ExtensionState.RUNNING
        )
        self.assertEqual(
            self.transport.probed_entrypoints, [descriptor.entrypoint_path]
        )

        message = self.adapter.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.type, MessageType.TEXT)
        self.assertEqual(message.channel.type, "telegram")
        self.assertEqual(message.channel.message_id, "81")
        self.assertEqual(message.channel.thread_id, "-90001")
        self.assertEqual(message.user.external_id, "10001")
        self.assertEqual(message.user.display_name, "Test User")
        self.assertEqual(message.session_id, "ses_telegram_-90001")
        self.assertEqual(message.content.text, "请处理这条Telegram测试消息")
        self.assertEqual(message.metadata["update_id"], 7001)
        self.assertEqual(message.metadata["bridge_mode"], "historical-external-process")

        receipt = self.adapter.send_response(message, "这是桥接层测试回复")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "9001")
        self.assertEqual(
            self.transport.sent,
            [("-90001", "这是桥接层测试回复")],
        )
        self.assertIsNone(self.adapter.receive_message())

        self.transport.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.STOPPED,
            reachable=False,
            detail="fake recovered Telegram process stopped",
        )
        stopped = self.adapter.health_check()
        self.assertFalse(stopped.healthy)
        self.assertEqual(stopped.code, "SERVICE_STOPPED")
        self.assertEqual(stopped.state, ExtensionState.ENABLED)
        self.assertEqual(
            self.lifecycle.get("telegram").state, ExtensionState.ENABLED
        )

        hashes_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }
        self.assertEqual(hashes_after, hashes_before)

    def test_non_text_update_is_rejected_without_calling_historical_code(self) -> None:
        update = {
            "update_id": 7002,
            "message": {
                "message_id": 82,
                "date": 1_700_000_001,
                "from": {"id": 10001},
                "chat": {"id": 10001, "type": "private"},
                "photo": [{"file_id": "not-downloaded"}],
            },
        }
        with self.assertRaisesRegex(ValueError, "supports text only"):
            self.adapter.parse_message(update)


if __name__ == "__main__":
    unittest.main()
