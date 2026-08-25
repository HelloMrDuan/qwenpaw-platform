from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.wechat_customer.runtime import WeChatCustomerRuntimeAdapter
from core.contracts import DeliveryStatus, MessageEvent, MessageType
from core.extensions import ExtensionRegistry
from core.extensions.lifecycle import ExtensionLifecycleManager
from core.extensions.runtime import (
    ExtensionGatewayOperation,
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
)
from scripts.build_extension import build_extension
from tests.runtime._agentscope_flow_support import AgentMock, build_receive_gateway


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer"
HISTORICAL_GATEWAY = PLUGIN_ROOT / "recovered" / "wecom_kf_gateway_v345.py"


class _FakeCustomerGateway:
    def __init__(self) -> None:
        self.events = [
            {
                "msgid": "customer-flow-1001",
                "msgtype": "text",
                "origin": 3,
                "external_userid": "wm-offline-user",
                "open_kfid": "wk-offline-service",
                "text": {"content": "你好，微信客服"},
                "gateway_delivery": {
                    "delivery_id": "gateway-customer-flow-1001",
                    "cursor_committed": True,
                    "db_claimed": True,
                },
            }
        ]
        self.requests: list[dict[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline customer gateway for {descriptor.name}",
        )

    def receive_event(self):
        return self.events.pop(0) if self.events else None

    def send_text(
        self, external_userid: str, open_kfid: str, text: str, reply_to: str
    ) -> str:
        self.requests.append(
            {
                "external_userid": external_userid,
                "open_kfid": open_kfid,
                "text": text,
                "reply_to": reply_to,
            }
        )
        return "customer-flow-reply-1002"


class WeChatCustomerAgentScopeFlowValidationTests(unittest.TestCase):
    def test_customer_adapter_gateway_agent_and_delivery_flow(self) -> None:
        source_hash = hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest()
        state_before = self._state_files()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry = ExtensionRegistry(REPOSITORY_ROOT)
            registry.discover()
            package = build_extension(PLUGIN_ROOT / "manifest.yaml", root / "dist")
            lifecycle = ExtensionLifecycleManager(root / "workspace" / "extensions")
            lifecycle.install(package.archive)
            transport = _FakeCustomerGateway()
            adapter = WeChatCustomerRuntimeAdapter(
                PluginRuntimeBridge(REPOSITORY_ROOT, registry, lifecycle, probe=transport),
                transport,
                instance_id="wechat-customer-agentscope-validation",
                clock=lambda: datetime(2026, 8, 25, 10, 5, tzinfo=timezone.utc),
            )
            gateway, metrics, traces = build_receive_gateway(
                registry, lifecycle, "wechat-customer", adapter
            )

            result = gateway.receive_message("wechat-customer")
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.operation, ExtensionGatewayOperation.RECEIVE_MESSAGE)
            self.assertIsInstance(result.value, MessageEvent)
            message = result.value
            identity = hashlib.sha256(
                b"wk-offline-service\0wm-offline-user"
            ).hexdigest()[:24]
            self.assertEqual(message.channel.type, "wechat-customer")
            self.assertEqual(
                message.channel.instance_id, "wechat-customer-agentscope-validation"
            )
            self.assertEqual(message.channel.tenant_id, "wk-offline-service")
            self.assertEqual(message.user.id, f"usr_wechat_customer_{identity}")
            self.assertEqual(message.user.external_id, "wm-offline-user")
            self.assertEqual(message.session_id, f"ses_wechat_customer_{identity}")
            self.assertEqual(message.conversation_id, f"conv_wechat_customer_{identity}")
            self.assertEqual(message.type, MessageType.TEXT)
            self.assertEqual(message.content.text, "你好，微信客服")
            self.assertTrue(message.metadata["cursor_committed"])
            self.assertTrue(message.metadata["db_claimed"])
            self.assertEqual(message.metadata["state_owner"], "gateway")
            self.assertEqual(result.context.trace_id, message.trace_id)
            self.assertEqual(result.context.session_id, message.session_id)

            agent = AgentMock("微信客服离线 Mock 回复")
            response = agent.respond(message)
            receipt = adapter.send_response(message, response)
            self.assertEqual(agent.received, [message])
            self.assertEqual(
                transport.requests,
                [
                    {
                        "external_userid": "wm-offline-user",
                        "open_kfid": "wk-offline-service",
                        "text": "微信客服离线 Mock 回复",
                        "reply_to": "customer-flow-1001",
                    }
                ],
            )
            self.assertEqual(receipt.channel, "wechat-customer")
            self.assertEqual(receipt.status, DeliveryStatus.SENT)
            self.assertEqual(receipt.session_id, message.session_id)
            self.assertEqual(receipt.provider_message_id, "customer-flow-reply-1002")
            self.assertEqual(receipt.metadata["state_owner"], "gateway")

            observed = metrics.get("wechat-customer")
            self.assertEqual((observed.calls, observed.successes, observed.failures), (1, 1, 0))
            self.assertEqual(
                [event.event_type for event in traces.trace(message.trace_id)],
                ["adapter.message.received"],
            )

        self.assertEqual(
            hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest(), source_hash
        )
        self.assertEqual(self._state_files(), state_before)

    @staticmethod
    def _state_files() -> tuple[str, ...]:
        patterns = ("*.db", "*.db-*", "*cursor*.json", "*cursor*.tmp")
        return tuple(
            sorted(
                str(path.relative_to(PLUGIN_ROOT))
                for pattern in patterns
                for path in PLUGIN_ROOT.rglob(pattern)
                if path.is_file()
            )
        )


if __name__ == "__main__":
    unittest.main()
