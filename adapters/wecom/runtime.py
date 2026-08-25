"""Safe facade from recovered WeCom SDK frames to MessageEvent."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, runtime_checkable

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
from core.extensions.lifecycle import HealthReport
from core.extensions.runtime.plugin_bridge import (
    ExternalServiceProbe,
    PluginRuntimeBridge,
)


Clock = Callable[[], datetime]


@runtime_checkable
class WeComBridgeTransport(ExternalServiceProbe, Protocol):
    """Injected facade for a future supervised historical WeCom process."""

    def receive_frame(self) -> Mapping[str, Any] | None:
        """Return one credential-free WeCom SDK message frame."""
        ...

    def send_reply(self, target_id: str, text: str, reply_to: str) -> str | None:
        """Forward text using an external SDK process and return provider id."""
        ...


class WeComRuntimeError(ValueError):
    """Raised when a recovered WeCom frame cannot cross the Message boundary."""


class WeComRuntimeAdapter:
    """Normalize historical WeCom frames without importing Node bridge code."""

    channel_type = "wecom"

    def __init__(
        self,
        plugin_bridge: PluginRuntimeBridge,
        transport: WeComBridgeTransport,
        *,
        instance_id: str = "wecom-recovered",
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(transport, WeComBridgeTransport):
            raise TypeError("transport must implement receive_frame/send_reply/check")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("instance_id must be non-empty text")
        self.plugin_bridge = plugin_bridge
        self.transport = transport
        self.instance_id = instance_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def receive_message(self) -> MessageEvent | None:
        frame = self.transport.receive_frame()
        if frame is None:
            return None
        return self.parse_message(frame)

    def parse_message(self, payload: Mapping[str, Any]) -> MessageEvent:
        if not isinstance(payload, Mapping):
            raise TypeError("WeCom SDK frame must be a mapping")
        body = payload.get("body")
        if not isinstance(body, Mapping):
            raise WeComRuntimeError("WeCom frame body is required")
        message_id = body.get("msgid")
        sender = body.get("from")
        text_block = body.get("text")
        if not isinstance(message_id, str) or not message_id.strip():
            raise WeComRuntimeError("WeCom body.msgid is required")
        if not isinstance(sender, Mapping):
            raise WeComRuntimeError("WeCom body.from is required")
        user_id = sender.get("userid")
        if not isinstance(user_id, str) or not user_id.strip():
            raise WeComRuntimeError("WeCom body.from.userid is required")
        text = (
            text_block.get("content") if isinstance(text_block, Mapping) else body.get("content")
        )
        if not isinstance(text, str) or not text.strip():
            raise WeComRuntimeError("historical WeCom Bridge supports text only")

        chat_type = str(body.get("chattype") or "single")
        if chat_type == "group":
            target = body.get("chatid")
            if not isinstance(target, str) or not target.strip():
                raise WeComRuntimeError("group WeCom message requires body.chatid")
            target_id = target
        else:
            target_id = user_id
        timestamp = self._timestamp()
        tenant_id = body.get("corpid")
        tenant = str(tenant_id) if tenant_id else None
        display_name = sender.get("name") or sender.get("username")
        return MessageEvent(
            id=f"msg_wecom_{message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=f"trc_wecom_{message_id}",
            channel=ChannelRef(
                type=self.channel_type,
                instance_id=self.instance_id,
                message_id=message_id,
                thread_id=target_id,
                tenant_id=tenant,
            ),
            user=UserRef(
                id=f"usr_wecom_{user_id}",
                external_id=user_id,
                display_name=str(display_name) if display_name else None,
                tenant_id=tenant,
            ),
            session_id=f"ses_wecom_{target_id}",
            conversation_id=f"conv_wecom_{target_id}",
            timestamp=timestamp,
            type=MessageType.TEXT,
            content=MessageContent(text=text),
            metadata={
                "provider": "wecom",
                "provider_message_id": message_id,
                "chat_type": chat_type,
                "target_id": target_id,
                "timestamp_source": "extension_received_at",
                "bridge_mode": "historical-external-process",
            },
        )

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        if not isinstance(message, MessageEvent):
            raise TypeError("message must be a MessageEvent")
        if message.channel.type != self.channel_type:
            raise WeComRuntimeError("MessageEvent is not from WeCom")
        if not isinstance(response, str) or not response.strip():
            raise WeComRuntimeError("response must be non-empty text")
        target_id = message.metadata.get("target_id") or message.channel.thread_id
        if not isinstance(target_id, str) or not target_id.strip():
            raise WeComRuntimeError("WeCom response requires target_id")
        provider_message_id = self.transport.send_reply(
            target_id,
            response,
            message.channel.message_id,
        )
        return DeliveryReceipt(
            delivery_id=f"delivery_wecom_{message.channel.message_id}",
            channel=self.channel_type,
            session_id=message.session_id,
            status=DeliveryStatus.SENT,
            provider_message_id=(
                str(provider_message_id) if provider_message_id is not None else None
            ),
            metadata={
                "target_id": target_id,
                "reply_to": message.channel.message_id,
                "bridge_mode": "historical-external-process",
            },
        )

    def health_check(self) -> HealthReport:
        return self.plugin_bridge.health("wecom", probe=self.transport)

    def _timestamp(self) -> str:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise WeComRuntimeError("clock must return a timezone-aware datetime")
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
