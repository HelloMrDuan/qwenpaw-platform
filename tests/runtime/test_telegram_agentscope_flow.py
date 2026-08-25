from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.telegram.runtime import TelegramRuntimeAdapter
from core.contracts import (
    MESSAGE_SCHEMA_VERSION,
    DeliveryStatus,
    MessageEvent,
    MessageType,
)
from core.extensions import ExtensionRegistry
from core.extensions.lifecycle import ExtensionLifecycleManager
from core.extensions.observability import ExtensionMetricsStore, ExtensionTraceStore
from core.extensions.runtime import (
    ExtensionGatewayOperation,
    ExtensionRuntimeGateway,
    ExternalServiceSnapshot,
    ExternalServiceState,
    PluginRuntimeBridge,
)
from core.streaming import StreamingBridge
from scripts.build_extension import build_extension


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TELEGRAM_ROOT = REPOSITORY_ROOT / "adapters" / "telegram"


class _FakeTelegramTransport:
    """Offline transport boundary; it never imports or calls the legacy Bridge."""

    def __init__(self, update: dict[str, object]) -> None:
        self._updates = [update]
        self.requests: list[dict[str, str]] = []

    def check(self, descriptor):
        return ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail=f"offline Telegram transport for {descriptor.name}",
        )

    def receive_update(self):
        return self._updates.pop(0) if self._updates else None

    def send_message(self, chat_id: str, text: str) -> str:
        self.requests.append(
            {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": text,
            }
        )
        return "10002"


class _AgentMock:
    def __init__(self) -> None:
        self.received: list[MessageEvent] = []

    def respond(self, message: MessageEvent) -> str:
        self.received.append(message)
        return "你好，这是离线 Agent Mock 回复"


class TelegramAgentScopeFlowValidationTests(unittest.TestCase):
    def test_existing_adapter_crosses_runtime_gateway_and_returns_receipt(self) -> None:
        update = {
            "update_id": 90001,
            "message": {
                "message_id": 10001,
                "date": 1_700_000_000,
                "chat": {"id": 20001, "type": "private"},
                "from": {"id": 30001, "first_name": "测试用户"},
                "text": "你好",
            },
        }
        historical_files = (
            TELEGRAM_ROOT / "recovered" / "telegram_bridge.py",
            TELEGRAM_ROOT / "recovered" / "telegram_bridge_main.py",
        )
        hashes_before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry = ExtensionRegistry(REPOSITORY_ROOT)
            registry.discover()
            package = build_extension(
                TELEGRAM_ROOT / "manifest.yaml",
                root / "dist",
            )
            lifecycle = ExtensionLifecycleManager(root / "workspace" / "extensions")
            lifecycle.install(package.archive)
            transport = _FakeTelegramTransport(update)
            adapter = TelegramRuntimeAdapter(
                PluginRuntimeBridge(
                    REPOSITORY_ROOT,
                    registry,
                    lifecycle,
                    probe=transport,
                ),
                transport,
                instance_id="telegram-agentscope-validation",
            )
            metrics = ExtensionMetricsStore()
            traces = ExtensionTraceStore()
            gateway = ExtensionRuntimeGateway(
                registry,
                lifecycle,
                skill_invoker=None,  # type: ignore[arg-type] -- receive-only test path
                streaming_bridge=StreamingBridge(),
                metrics_store=metrics,
                trace_store=traces,
                message_receivers={"telegram": adapter},
                id_factory=iter(("provisional-trace", "provisional-session", "event-1")).__next__,
            )

            received = gateway.receive_message("telegram")
            self.assertIsNotNone(received)
            assert received is not None
            self.assertEqual(received.operation, ExtensionGatewayOperation.RECEIVE_MESSAGE)
            self.assertIsInstance(received.value, MessageEvent)
            message = received.value

            self.assertEqual(message.version, MESSAGE_SCHEMA_VERSION)
            self.assertEqual(message.id, "msg_telegram_20001_10001")
            self.assertEqual(message.trace_id, "trc_telegram_90001")
            self.assertEqual(message.channel.type, "telegram")
            self.assertEqual(message.channel.instance_id, "telegram-agentscope-validation")
            self.assertEqual(message.channel.message_id, "10001")
            self.assertEqual(message.channel.thread_id, "20001")
            self.assertEqual(message.user.id, "usr_telegram_30001")
            self.assertEqual(message.user.external_id, "30001")
            self.assertEqual(message.session_id, "ses_telegram_20001")
            self.assertEqual(message.conversation_id, "conv_telegram_20001")
            self.assertEqual(message.type, MessageType.TEXT)
            self.assertEqual(message.content.text, "你好")
            self.assertEqual(message.attachments, ())
            self.assertEqual(message.metadata["update_id"], 90001)
            self.assertEqual(message.metadata["chat_id"], "20001")
            self.assertEqual(received.context.trace_id, message.trace_id)
            self.assertEqual(received.context.session_id, message.session_id)

            agent = _AgentMock()
            response = agent.respond(message)
            receipt = adapter.send_response(message, response)

            self.assertEqual(agent.received, [message])
            self.assertEqual(
                transport.requests,
                [
                    {
                        "method": "sendMessage",
                        "chat_id": "20001",
                        "text": "你好，这是离线 Agent Mock 回复",
                    }
                ],
            )
            self.assertEqual(receipt.delivery_id, "delivery_telegram_10001")
            self.assertEqual(receipt.channel, "telegram")
            self.assertEqual(receipt.session_id, "ses_telegram_20001")
            self.assertEqual(receipt.status, DeliveryStatus.SENT)
            self.assertEqual(receipt.provider_message_id, "10002")
            self.assertEqual(receipt.metadata["chat_id"], "20001")

            telegram_metrics = metrics.get("telegram")
            self.assertEqual(telegram_metrics.calls, 1)
            self.assertEqual(telegram_metrics.successes, 1)
            self.assertEqual(telegram_metrics.failures, 0)
            trace_events = traces.trace("trc_telegram_90001", extension_name="telegram")
            self.assertEqual(
                [event.event_type for event in trace_events],
                ["adapter.message.received"],
            )

        hashes_after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in historical_files
        }
        self.assertEqual(hashes_after, hashes_before)


if __name__ == "__main__":
    unittest.main()
