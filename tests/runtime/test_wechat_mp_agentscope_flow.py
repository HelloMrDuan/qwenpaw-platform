from __future__ import annotations

from datetime import datetime, timezone
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
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-mp"
HISTORICAL_GATEWAY = PLUGIN_ROOT / "recovered" / "wechat_mp_gateway.py"


class _FakeWeChatMpTransport:
    def __init__(self) -> None:
        self.messages = [
            {
                "MsgId": "mp-flow-1001",
                "CreateTime": 1_700_000_000,
                "FromUserName": "openid-offline-user",
                "ToUserName": "gh-offline-account",
                "MsgType": "text",
                "Content": "你好，微信公众号",
            }
        ]
        self.requests: list[dict[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline WeChat MP facade for {descriptor.name}",
        )

    def receive_message(self):
        return self.messages.pop(0) if self.messages else None

    def send_reply(self, to_user: str, from_user: str, text: str) -> str:
        self.requests.append(
            {
                "ToUserName": to_user,
                "FromUserName": from_user,
                "MsgType": "text",
                "Content": text,
            }
        )
        return "mp-flow-reply-1002"


class _OfflineWeChatMpContractFacade:
    """Test-only decoded callback facade; the recovered Gateway is never imported."""

    channel_type = "wechat-mp"

    def __init__(self, bridge: PluginRuntimeBridge, transport: _FakeWeChatMpTransport):
        self.bridge = bridge
        self.transport = transport

    def receive_message(self) -> MessageEvent | None:
        payload = self.transport.receive_message()
        return None if payload is None else self.parse_message(payload)

    def parse_message(self, payload) -> MessageEvent:
        required = ("MsgId", "FromUserName", "ToUserName", "Content")
        if payload.get("MsgType") != "text" or any(not payload.get(key) for key in required):
            raise ValueError("offline WeChat MP fixture requires a complete text callback")
        timestamp = datetime.fromtimestamp(
            payload["CreateTime"], timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        user_id = str(payload["FromUserName"])
        account_id = str(payload["ToUserName"])
        message_id = str(payload["MsgId"])
        identity = hashlib.sha256(
            f"{account_id}\0{user_id}".encode("utf-8")
        ).hexdigest()[:24]
        return MessageEvent(
            id=f"msg_wechat_mp_{message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=f"trc_wechat_mp_{message_id}",
            channel=ChannelRef(
                type=self.channel_type,
                instance_id="wechat-mp-agentscope-validation",
                message_id=message_id,
                thread_id=user_id,
                tenant_id=account_id,
            ),
            user=UserRef(
                id=f"usr_wechat_mp_{identity}",
                external_id=user_id,
                tenant_id=account_id,
            ),
            session_id=f"ses_wechat_mp_{identity}",
            conversation_id=f"conv_wechat_mp_{identity}",
            timestamp=timestamp,
            type=MessageType.TEXT,
            content=MessageContent(text=str(payload["Content"])),
            metadata={
                "provider": "wechat-mp",
                "to_user": account_id,
                "from_user": user_id,
                "validation_mode": "decoded-callback-contract-fixture",
            },
        )

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        provider_id = self.transport.send_reply(
            message.user.external_id,
            str(message.channel.tenant_id),
            response,
        )
        return DeliveryReceipt(
            delivery_id=f"delivery_wechat_mp_{message.channel.message_id}",
            channel=self.channel_type,
            session_id=message.session_id,
            status=DeliveryStatus.SENT,
            provider_message_id=provider_id,
            metadata={"reply_mode": "passive-xml-contract-fixture"},
        )

    def health_check(self):
        return self.bridge.health("wechat-mp", probe=self.transport)


class WeChatMpAgentScopeFlowValidationTests(unittest.TestCase):
    def test_wechat_mp_contract_gateway_agent_and_delivery_flow(self) -> None:
        source_hash = hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest()
        registry = ExtensionRegistry(REPOSITORY_ROOT)
        registry.discover()
        metadata = registry.get("wechat-mp")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        lifecycle = StaticRunningLifecycle(metadata)
        transport = _FakeWeChatMpTransport()
        bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT, registry, lifecycle, probe=transport
        )
        self.assertEqual(bridge.describe("wechat-mp").entrypoint_path, HISTORICAL_GATEWAY)
        facade = _OfflineWeChatMpContractFacade(bridge, transport)
        gateway, metrics, traces = build_receive_gateway(
            registry, lifecycle, "wechat-mp", facade
        )

        result = gateway.receive_message("wechat-mp")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.operation, ExtensionGatewayOperation.RECEIVE_MESSAGE)
        self.assertIsInstance(result.value, MessageEvent)
        message = result.value
        identity = hashlib.sha256(
            b"gh-offline-account\0openid-offline-user"
        ).hexdigest()[:24]
        self.assertEqual(message.channel.type, "wechat-mp")
        self.assertEqual(message.channel.message_id, "mp-flow-1001")
        self.assertEqual(message.channel.thread_id, "openid-offline-user")
        self.assertEqual(message.channel.tenant_id, "gh-offline-account")
        self.assertEqual(message.user.id, f"usr_wechat_mp_{identity}")
        self.assertEqual(message.user.external_id, "openid-offline-user")
        self.assertEqual(message.session_id, f"ses_wechat_mp_{identity}")
        self.assertEqual(message.conversation_id, f"conv_wechat_mp_{identity}")
        self.assertEqual(message.type, MessageType.TEXT)
        self.assertEqual(message.content.text, "你好，微信公众号")
        self.assertEqual(result.context.trace_id, message.trace_id)
        self.assertEqual(result.context.session_id, message.session_id)

        agent = AgentMock("微信公众号离线 Mock 回复")
        response = agent.respond(message)
        receipt = facade.send_response(message, response)
        self.assertEqual(agent.received, [message])
        self.assertEqual(
            transport.requests,
            [
                {
                    "ToUserName": "openid-offline-user",
                    "FromUserName": "gh-offline-account",
                    "MsgType": "text",
                    "Content": "微信公众号离线 Mock 回复",
                }
            ],
        )
        self.assertEqual(receipt.channel, "wechat-mp")
        self.assertEqual(receipt.status, DeliveryStatus.SENT)
        self.assertEqual(receipt.session_id, message.session_id)
        self.assertEqual(receipt.provider_message_id, "mp-flow-reply-1002")

        observed = metrics.get("wechat-mp")
        self.assertEqual((observed.calls, observed.successes, observed.failures), (1, 1, 0))
        self.assertEqual(
            [event.event_type for event in traces.trace(message.trace_id)],
            ["adapter.message.received"],
        )
        self.assertEqual(
            hashlib.sha256(HISTORICAL_GATEWAY.read_bytes()).hexdigest(), source_hash
        )


if __name__ == "__main__":
    unittest.main()
