from __future__ import annotations

import hashlib
from itertools import count
from pathlib import Path
import unittest

from adapters.wechat_customer.runtime import WeChatCustomerRuntimeAdapter
from core.contracts import DeliveryStatus
from core.extensions import ExtensionRegistry
from core.extensions.observability import ExtensionMetricsStore, ExtensionTraceStore
from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
from core.streaming import StreamingBridge
from core.extensions.runtime import ExtensionRuntimeGateway
from tests.runtime._agentscope_flow_support import StaticRunningLifecycle


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATEWAY = REPOSITORY_ROOT / "plugins" / "wechat-customer" / "recovered" / "wecom_kf_gateway_v345.py"
ADAPTER = REPOSITORY_ROOT / "adapters" / "wechat_customer" / "runtime.py"


def _event(message_id="bridge-1", external_userid="customer-1", open_kfid="kf-1"):
    return {
        "msgid": message_id,
        "msgtype": "text",
        "origin": 3,
        "external_userid": external_userid,
        "open_kfid": open_kfid,
        "text": {"content": "Gateway Bridge 离线消息"},
        "gateway_delivery": {
            "delivery_id": f"delivery-{message_id}",
            "cursor_committed": True,
            "db_claimed": True,
        },
    }


class _Transport:
    def __init__(self):
        self.events = [_event()]
        self.sent = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline bridge for {descriptor.name}",
        )

    def receive_event(self):
        return self.events.pop(0) if self.events else None

    def send_text(self, external_userid, open_kfid, text, reply_to):
        self.sent.append((external_userid, open_kfid, text, reply_to))
        return "bridge-provider-reply"


class _PluginBridge:
    def __init__(self, lifecycle):
        self.lifecycle = lifecycle

    def health(self, name, probe=None):
        del probe
        return self.lifecycle.health(name)


class WeChatCustomerGatewayBridgeTests(unittest.TestCase):
    def test_gateway_adapter_runtime_trace_metrics_and_history_hashes(self):
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (GATEWAY, ADAPTER)}
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.discover()
        metadata = registry.get("wechat-customer")
        self.assertIsNotNone(metadata)
        lifecycle = StaticRunningLifecycle(metadata)
        transport = _Transport()
        adapter = WeChatCustomerRuntimeAdapter(
            _PluginBridge(lifecycle),
            transport,
            instance_id="wechat-customer-native-bridge-test",
        )
        metrics = ExtensionMetricsStore()
        traces = ExtensionTraceStore()
        ids = count(1)
        gateway = ExtensionRuntimeGateway(
            registry,
            lifecycle,
            skill_invoker=None,
            streaming_bridge=StreamingBridge(),
            metrics_store=metrics,
            trace_store=traces,
            message_receivers={"wechat-customer": adapter},
            id_factory=lambda: f"wechat-bridge-{next(ids)}",
        )

        result = gateway.receive_message("wechat-customer")
        self.assertIsNotNone(result)
        message = result.value
        self.assertEqual(message.session_id, adapter.parse_message(_event("bridge-2")).session_id)
        self.assertNotEqual(message.session_id, adapter.parse_message(_event("bridge-3", "customer-2")).session_id)
        self.assertNotEqual(message.session_id, adapter.parse_message(_event("bridge-4", open_kfid="kf-2")).session_id)
        self.assertEqual(metrics.get("wechat-customer").successes, 1)
        trace = traces.trace(message.trace_id)
        self.assertEqual(trace[-1].event_type, "adapter.message.received")

        receipt = adapter.send_response(message, "Gateway Bridge 最终回复")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.provider_message_id, "bridge-provider-reply")
        self.assertEqual(transport.sent[0][:3], ("customer-1", "kf-1", "Gateway Bridge 最终回复"))

        forbidden = _event("bridge-cursor")
        forbidden["cursor"] = "must-stay-in-gateway"
        with self.assertRaisesRegex(ValueError, "cursor values must not cross"):
            adapter.parse_message(forbidden)

        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (GATEWAY, ADAPTER)}
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
