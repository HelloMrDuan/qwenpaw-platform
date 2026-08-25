from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.wecom.runtime import WeComRuntimeAdapter
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
WECOM_ROOT = REPOSITORY_ROOT / "plugins" / "wecom"


class _FakeWeComTransport:
    def __init__(self) -> None:
        self.frames = [
            {
                "body": {
                    "msgid": "wecom-flow-1001",
                    "chattype": "group",
                    "chatid": "group-flow-01",
                    "corpid": "corp-offline",
                    "from": {"userid": "user-offline", "name": "离线用户"},
                    "text": {"content": "你好，企业微信"},
                }
            }
        ]
        self.requests: list[dict[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline WeCom transport for {descriptor.name}",
        )

    def receive_frame(self):
        return self.frames.pop(0) if self.frames else None

    def send_reply(self, target_id: str, text: str, reply_to: str) -> str:
        self.requests.append(
            {"target_id": target_id, "text": text, "reply_to": reply_to}
        )
        return "wecom-flow-reply-1002"


class WeComAgentScopeFlowValidationTests(unittest.TestCase):
    def test_wecom_adapter_gateway_agent_and_delivery_flow(self) -> None:
        historical_files = (
            WECOM_ROOT / "recovered" / "wecom-node" / "wecom_bridge.mjs",
            WECOM_ROOT / "recovered" / "wecom-node" / "bot.mjs",
        )
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry = ExtensionRegistry(REPOSITORY_ROOT)
            registry.discover()
            package = build_extension(WECOM_ROOT / "manifest.yaml", root / "dist")
            lifecycle = ExtensionLifecycleManager(root / "workspace" / "extensions")
            lifecycle.install(package.archive)
            transport = _FakeWeComTransport()
            adapter = WeComRuntimeAdapter(
                PluginRuntimeBridge(REPOSITORY_ROOT, registry, lifecycle, probe=transport),
                transport,
                instance_id="wecom-agentscope-validation",
                clock=lambda: datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc),
            )
            gateway, metrics, traces = build_receive_gateway(
                registry, lifecycle, "wecom", adapter
            )

            result = gateway.receive_message("wecom")
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.operation, ExtensionGatewayOperation.RECEIVE_MESSAGE)
            self.assertIsInstance(result.value, MessageEvent)
            message = result.value
            self.assertEqual(message.channel.type, "wecom")
            self.assertEqual(message.channel.instance_id, "wecom-agentscope-validation")
            self.assertEqual(message.channel.message_id, "wecom-flow-1001")
            self.assertEqual(message.channel.thread_id, "group-flow-01")
            self.assertEqual(message.channel.tenant_id, "corp-offline")
            self.assertEqual(message.user.id, "usr_wecom_user-offline")
            self.assertEqual(message.user.external_id, "user-offline")
            self.assertEqual(message.session_id, "ses_wecom_group-flow-01")
            self.assertEqual(message.conversation_id, "conv_wecom_group-flow-01")
            self.assertEqual(message.type, MessageType.TEXT)
            self.assertEqual(message.content.text, "你好，企业微信")
            self.assertEqual(message.metadata["target_id"], "group-flow-01")
            self.assertEqual(result.context.trace_id, message.trace_id)
            self.assertEqual(result.context.session_id, message.session_id)

            agent = AgentMock("企业微信离线 Mock 回复")
            response = agent.respond(message)
            receipt = adapter.send_response(message, response)
            self.assertEqual(agent.received, [message])
            self.assertEqual(
                transport.requests,
                [
                    {
                        "target_id": "group-flow-01",
                        "text": "企业微信离线 Mock 回复",
                        "reply_to": "wecom-flow-1001",
                    }
                ],
            )
            self.assertEqual(receipt.channel, "wecom")
            self.assertEqual(receipt.status, DeliveryStatus.SENT)
            self.assertEqual(receipt.session_id, message.session_id)
            self.assertEqual(receipt.provider_message_id, "wecom-flow-reply-1002")

            observed = metrics.get("wecom")
            self.assertEqual((observed.calls, observed.successes, observed.failures), (1, 1, 0))
            self.assertEqual(
                [event.event_type for event in traces.trace(message.trace_id)],
                ["adapter.message.received"],
            )

        self.assertEqual(
            {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in historical_files
            },
            hashes_before,
        )


if __name__ == "__main__":
    unittest.main()
