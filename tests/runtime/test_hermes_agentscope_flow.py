from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from core.contracts import (
    MESSAGE_SCHEMA_VERSION,
    ChannelRef,
    DeliveryReceipt,
    DeliveryStatus,
    MessageContent,
    MessageEvent,
    MessageType,
    UserRef,
)
from core.extensions import ExtensionRegistry
from core.extensions.runtime import (
    ExtensionGatewayOperation,
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
)
from tests.runtime._agentscope_flow_support import (
    AgentMock,
    StaticRunningLifecycle,
    build_receive_gateway,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "hermes"
HISTORICAL_ENTRYPOINT = (
    PLUGIN_ROOT / "recovered" / "hermes-agent-main" / "gateway" / "run.py"
)


class _FakeHermesTransport:
    def __init__(self) -> None:
        self.events = [
            {
                "message_id": "hermes-flow-1001",
                "user_id": "hermes-offline-user",
                "session_key": "gateway-session-01",
                "timestamp": "2026-08-25T10:15:00Z",
                "text": "你好，Hermes",
            }
        ]
        self.requests: list[dict[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline Hermes facade for {descriptor.name}",
        )

    def receive_event(self):
        return self.events.pop(0) if self.events else None

    def send_response(self, session_key: str, text: str, reply_to: str) -> str:
        self.requests.append(
            {"session_key": session_key, "text": text, "reply_to": reply_to}
        )
        return "hermes-flow-reply-1002"


class _OfflineHermesContractFacade:
    """Test-only gateway envelope facade; Hermes source is never imported."""

    channel_type = "hermes"

    def __init__(self, bridge: PluginRuntimeBridge, transport: _FakeHermesTransport):
        self.bridge = bridge
        self.transport = transport

    def receive_message(self) -> MessageEvent | None:
        payload = self.transport.receive_event()
        return None if payload is None else self.parse_message(payload)

    def parse_message(self, payload) -> MessageEvent:
        required = ("message_id", "user_id", "session_key", "timestamp", "text")
        if any(not payload.get(key) for key in required):
            raise ValueError("offline Hermes fixture requires a complete text envelope")
        message_id = str(payload["message_id"])
        user_id = str(payload["user_id"])
        session_key = str(payload["session_key"])
        return MessageEvent(
            id=f"msg_hermes_{message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=f"trc_hermes_{message_id}",
            channel=ChannelRef(
                type=self.channel_type,
                instance_id="hermes-agentscope-validation",
                message_id=message_id,
                thread_id=session_key,
            ),
            user=UserRef(
                id=f"usr_hermes_{user_id}",
                external_id=user_id,
            ),
            session_id=f"ses_hermes_{session_key}",
            conversation_id=f"conv_hermes_{session_key}",
            timestamp=str(payload["timestamp"]),
            type=MessageType.TEXT,
            content=MessageContent(text=str(payload["text"])),
            metadata={
                "provider": "hermes",
                "session_key": session_key,
                "validation_mode": "gateway-envelope-contract-fixture",
            },
        )

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        session_key = str(message.metadata["session_key"])
        provider_id = self.transport.send_response(
            session_key, response, message.channel.message_id
        )
        return DeliveryReceipt(
            delivery_id=f"delivery_hermes_{message.channel.message_id}",
            channel=self.channel_type,
            session_id=message.session_id,
            status=DeliveryStatus.SENT,
            provider_message_id=provider_id,
            metadata={"session_key": session_key},
        )

    def health_check(self):
        return self.bridge.health("hermes", probe=self.transport)


class HermesAgentScopeFlowValidationTests(unittest.TestCase):
    def test_hermes_contract_gateway_agent_and_delivery_flow(self) -> None:
        source_hash = hashlib.sha256(HISTORICAL_ENTRYPOINT.read_bytes()).hexdigest()
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.discover()
        metadata = registry.get("hermes")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        lifecycle = StaticRunningLifecycle(metadata)
        transport = _FakeHermesTransport()
        bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT, registry, lifecycle, probe=transport
        )
        self.assertEqual(bridge.describe("hermes").entrypoint_path, HISTORICAL_ENTRYPOINT)
        facade = _OfflineHermesContractFacade(bridge, transport)
        gateway, metrics, traces = build_receive_gateway(
            registry, lifecycle, "hermes", facade
        )

        result = gateway.receive_message("hermes")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.operation, ExtensionGatewayOperation.RECEIVE_MESSAGE)
        self.assertIsInstance(result.value, MessageEvent)
        message = result.value
        self.assertEqual(message.channel.type, "hermes")
        self.assertEqual(message.channel.message_id, "hermes-flow-1001")
        self.assertEqual(message.channel.thread_id, "gateway-session-01")
        self.assertEqual(message.user.id, "usr_hermes_hermes-offline-user")
        self.assertEqual(message.user.external_id, "hermes-offline-user")
        self.assertEqual(message.session_id, "ses_hermes_gateway-session-01")
        self.assertEqual(message.conversation_id, "conv_hermes_gateway-session-01")
        self.assertEqual(message.type, MessageType.TEXT)
        self.assertEqual(message.content.text, "你好，Hermes")
        self.assertEqual(result.context.trace_id, message.trace_id)
        self.assertEqual(result.context.session_id, message.session_id)

        agent = AgentMock("Hermes 离线 Mock 回复")
        response = agent.respond(message)
        receipt = facade.send_response(message, response)
        self.assertEqual(agent.received, [message])
        self.assertEqual(
            transport.requests,
            [
                {
                    "session_key": "gateway-session-01",
                    "text": "Hermes 离线 Mock 回复",
                    "reply_to": "hermes-flow-1001",
                }
            ],
        )
        self.assertEqual(receipt.channel, "hermes")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.session_id, message.session_id)
        self.assertEqual(receipt.provider_message_id, "hermes-flow-reply-1002")

        observed = metrics.get("hermes")
        self.assertEqual((observed.calls, observed.successes, observed.failures), (1, 1, 0))
        self.assertEqual(
            [event.event_type for event in traces.trace(message.trace_id)],
            ["adapter.message.received"],
        )
        self.assertEqual(
            hashlib.sha256(HISTORICAL_ENTRYPOINT.read_bytes()).hexdigest(), source_hash
        )


if __name__ == "__main__":
    unittest.main()
