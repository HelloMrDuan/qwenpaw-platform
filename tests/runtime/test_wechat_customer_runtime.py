from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.wechat_customer.runtime import (
    WeChatCustomerRuntimeAdapter,
    WeChatCustomerRuntimeError,
)
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
GATEWAY_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer"
HISTORICAL_GATEWAY = GATEWAY_ROOT / "recovered" / "wecom_kf_gateway_v345.py"


def _gateway_event(
    *,
    message_id: str = "kf-msg-1001",
    external_userid: str = "wm-customer-001",
    open_kfid: str = "wk-service-001",
) -> dict[str, object]:
    return {
        "msgid": message_id,
        "msgtype": "text",
        "origin": 3,
        "external_userid": external_userid,
        "open_kfid": open_kfid,
        "text": {"content": "请处理这条微信客服测试消息"},
        "gateway_delivery": {
            "delivery_id": f"gateway-{message_id}",
            "cursor_committed": True,
            "db_claimed": True,
        },
    }


class _FakeWeChatCustomerGateway:
    def __init__(self) -> None:
        self.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail="fake WeChat Customer Gateway health endpoint is reachable",
        )
        self.events = [_gateway_event()]
        self.sent: list[tuple[str, str, str, str]] = []
        self.probed_entrypoints: list[Path] = []

    def check(self, descriptor):
        self.probed_entrypoints.append(descriptor.entrypoint_path)
        return self.snapshot

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
        return "kf-reply-9001"


class WeChatCustomerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.package_output = self.root / "dist"
        self.deployments = self.root / "workspace" / "extensions"
        self.registry = ExtensionRegistry(REPOSITORY_ROOT)
        self.discovered = self.registry.discover()
        self.package = build_extension(
            GATEWAY_ROOT / "manifest.yaml", self.package_output
        )
        self.lifecycle = ExtensionLifecycleManager(self.deployments)
        self.lifecycle.install(self.package.archive)
        self.transport = _FakeWeChatCustomerGateway()
        self.plugin_bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT,
            self.registry,
            self.lifecycle,
            probe=self.transport,
        )
        self.adapter = WeChatCustomerRuntimeAdapter(
            self.plugin_bridge,
            self.transport,
            instance_id="wechat-customer-runtime-test",
            clock=lambda: datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_gateway_discovery_health_message_and_response_round_trip(self) -> None:
        source_hash = hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest()
        state_files_before = self._gateway_state_files()

        metadata = self.registry.get("wechat-customer")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertIn(metadata, self.discovered)
        self.assertEqual(metadata.type, ExtensionType.PLUGIN)
        self.assertEqual(metadata.runtime, ExtensionRuntime.PYTHON)
        self.assertEqual(
            metadata.entrypoint,
            "recovered/wecom_kf_gateway_v345.py",
        )
        self.assertEqual(
            metadata.healthcheck,
            {
                "type": "http",
                "target": "http://127.0.0.1:8798/healthz",
            },
        )

        descriptor = self.plugin_bridge.describe("wechat-customer")
        self.assertEqual(descriptor.name, "wechat-customer")
        self.assertEqual(descriptor.entrypoint_path, HISTORICAL_GATEWAY)

        health = self.adapter.health_check()
        self.assertTrue(health.healthy)
        self.assertTrue(health.deployment_verified)
        self.assertTrue(health.runtime_probe_performed)
        self.assertEqual(health.code, "SERVICE_RUNNING")
        self.assertEqual(health.state, ExtensionState.RUNNING)
        self.assertEqual(
            self.lifecycle.get("wechat-customer").state,
            ExtensionState.RUNNING,
        )
        self.assertEqual(
            self.transport.probed_entrypoints,
            [HISTORICAL_GATEWAY],
        )

        message = self.adapter.receive_message()
        self.assertIsInstance(message, MessageEvent)
        assert message is not None
        self.assertEqual(message.type, MessageType.TEXT)
        self.assertEqual(message.channel.type, "wechat-customer")
        self.assertEqual(message.channel.message_id, "kf-msg-1001")
        self.assertEqual(message.channel.tenant_id, "wk-service-001")
        self.assertEqual(message.user.external_id, "wm-customer-001")
        self.assertEqual(message.timestamp, "2026-08-25T09:00:00Z")
        self.assertEqual(message.content.text, "请处理这条微信客服测试消息")
        self.assertTrue(message.metadata["cursor_committed"])
        self.assertTrue(message.metadata["db_claimed"])
        self.assertEqual(message.metadata["state_owner"], "gateway")
        self.assertNotIn("wm-customer-001", message.session_id)

        receipt = self.adapter.send_response(message, "这是微信客服桥接层测试回复")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "kf-reply-9001")
        self.assertEqual(receipt.session_id, message.session_id)
        self.assertEqual(receipt.metadata["state_owner"], "gateway")
        self.assertEqual(
            self.transport.sent,
            [
                (
                    "wm-customer-001",
                    "wk-service-001",
                    "这是微信客服桥接层测试回复",
                    "kf-msg-1001",
                )
            ],
        )
        self.assertIsNone(self.adapter.receive_message())

        self.transport.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.STOPPED,
            reachable=False,
            detail="fake WeChat Customer Gateway stopped",
        )
        stopped = self.adapter.health_check()
        self.assertFalse(stopped.healthy)
        self.assertEqual(stopped.code, "SERVICE_STOPPED")
        self.assertEqual(stopped.state, ExtensionState.ENABLED)

        self.assertEqual(
            hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest(),
            source_hash,
        )
        self.assertEqual(self._gateway_state_files(), state_files_before)

    def test_session_mapping_is_stable_and_scoped_by_customer_service_account(self) -> None:
        first = self.adapter.parse_message(_gateway_event(message_id="kf-msg-a"))
        second = self.adapter.parse_message(_gateway_event(message_id="kf-msg-b"))
        other_customer = self.adapter.parse_message(
            _gateway_event(message_id="kf-msg-c", external_userid="wm-customer-002")
        )
        other_account = self.adapter.parse_message(
            _gateway_event(message_id="kf-msg-d", open_kfid="wk-service-002")
        )

        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(first.conversation_id, second.conversation_id)
        self.assertNotEqual(first.session_id, other_customer.session_id)
        self.assertNotEqual(first.session_id, other_account.session_id)
        self.assertEqual(len(first.session_id.removeprefix("ses_wechat_customer_")), 24)

    def test_cursor_and_database_ownership_guards(self) -> None:
        with_cursor = _gateway_event(message_id="kf-msg-cursor")
        with_cursor["next_cursor"] = "must-not-cross-boundary"
        with self.assertRaisesRegex(
            WeChatCustomerRuntimeError, "cursor values must not cross"
        ):
            self.adapter.parse_message(with_cursor)

        not_committed = _gateway_event(message_id="kf-msg-uncommitted")
        not_committed["gateway_delivery"]["cursor_committed"] = False
        with self.assertRaisesRegex(
            WeChatCustomerRuntimeError, "persist its cursor"
        ):
            self.adapter.parse_message(not_committed)

        not_claimed = _gateway_event(message_id="kf-msg-unclaimed")
        not_claimed["gateway_delivery"]["db_claimed"] = False
        with self.assertRaisesRegex(
            WeChatCustomerRuntimeError, "claim the message"
        ):
            self.adapter.parse_message(not_claimed)

        leaked_delivery_state = _gateway_event(message_id="kf-msg-leak")
        leaked_delivery_state["gateway_delivery"]["cursor"] = "not-allowed"
        with self.assertRaisesRegex(
            WeChatCustomerRuntimeError, "unsupported state fields"
        ):
            self.adapter.parse_message(leaked_delivery_state)

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
