"""Safe facade from the recovered Telegram Bridge shape to MessageEvent."""

from __future__ import annotations

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


@runtime_checkable
class TelegramBridgeTransport(ExternalServiceProbe, Protocol):
    """Injected facade implemented by tests or a future supervised process client."""

    def receive_update(self) -> Mapping[str, Any] | None:
        """Return one Telegram Update JSON object, without exposing a token."""
        ...

    def send_message(self, chat_id: str, text: str) -> str | None:
        """Forward a plain-text response and return a provider message id."""
        ...


class TelegramRuntimeError(ValueError):
    """Raised when a historical Telegram payload cannot cross the Message boundary."""


class TelegramRuntimeAdapter:
    """Bridge Telegram Update/response shapes without importing legacy scripts."""

    channel_type = "telegram"

    def __init__(
        self,
        plugin_bridge: PluginRuntimeBridge,
        transport: TelegramBridgeTransport,
        *,
        instance_id: str = "telegram-recovered",
    ) -> None:
        if not isinstance(transport, TelegramBridgeTransport):
            raise TypeError("transport must implement receive_update/send_message/check")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("instance_id must be non-empty text")
        self.plugin_bridge = plugin_bridge
        self.transport = transport
        self.instance_id = instance_id

    def receive_message(self) -> MessageEvent | None:
        update = self.transport.receive_update()
        if update is None:
            return None
        return self.parse_message(update)

    def parse_message(self, payload: Mapping[str, Any]) -> MessageEvent:
        if not isinstance(payload, Mapping):
            raise TypeError("Telegram Update must be a mapping")
        update_id = payload.get("update_id")
        if type(update_id) is not int:
            raise TelegramRuntimeError("Telegram update_id must be an integer")
        message = payload.get("message") or payload.get("edited_message")
        if not isinstance(message, Mapping):
            raise TelegramRuntimeError("Telegram Update does not contain a message")
        message_id = message.get("message_id")
        timestamp = message.get("date")
        chat = message.get("chat")
        user = message.get("from")
        text = message.get("text")
        if type(message_id) is not int:
            raise TelegramRuntimeError("Telegram message_id must be an integer")
        if type(timestamp) is not int or timestamp < 0:
            raise TelegramRuntimeError("Telegram message date must be a Unix timestamp")
        if not isinstance(chat, Mapping) or type(chat.get("id")) is not int:
            raise TelegramRuntimeError("Telegram message chat.id is required")
        if not isinstance(user, Mapping) or type(user.get("id")) is not int:
            raise TelegramRuntimeError("Telegram message from.id is required")
        if not isinstance(text, str) or not text.strip():
            raise TelegramRuntimeError("historical Telegram Bridge supports text only")

        chat_id = str(chat["id"])
        user_id = str(user["id"])
        provider_message_id = str(message_id)
        display_name = self._display_name(user)
        try:
            utc_timestamp = (
                datetime.fromtimestamp(timestamp, timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
        except (OverflowError, OSError, ValueError) as exc:
            raise TelegramRuntimeError("Telegram message date is out of range") from exc
        return MessageEvent(
            id=f"msg_telegram_{chat_id}_{provider_message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=f"trc_telegram_{update_id}",
            channel=ChannelRef(
                type=self.channel_type,
                instance_id=self.instance_id,
                message_id=provider_message_id,
                thread_id=chat_id,
            ),
            user=UserRef(
                id=f"usr_telegram_{user_id}",
                external_id=user_id,
                display_name=display_name,
            ),
            session_id=f"ses_telegram_{chat_id}",
            conversation_id=f"conv_telegram_{chat_id}",
            timestamp=utc_timestamp,
            type=MessageType.TEXT,
            content=MessageContent(text=text),
            metadata={
                "provider": "telegram",
                "update_id": update_id,
                "chat_id": chat_id,
                "chat_type": chat.get("type"),
                "provider_message_id": provider_message_id,
                "edited": "edited_message" in payload and "message" not in payload,
                "bridge_mode": "historical-external-process",
            },
        )

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        if not isinstance(message, MessageEvent):
            raise TypeError("message must be a MessageEvent")
        if message.channel.type != self.channel_type:
            raise TelegramRuntimeError("MessageEvent is not from Telegram")
        if not isinstance(response, str) or not response.strip():
            raise TelegramRuntimeError("response must be non-empty text")
        chat_id = message.metadata.get("chat_id") or message.channel.thread_id
        if chat_id is None:
            raise TelegramRuntimeError("Telegram response requires chat_id")
        provider_message_id = self.transport.send_message(str(chat_id), response)
        return DeliveryReceipt(
            delivery_id=f"delivery_telegram_{message.channel.message_id}",
            channel=self.channel_type,
            session_id=message.session_id,
            status=DeliveryStatus.SENT,
            provider_message_id=(
                str(provider_message_id) if provider_message_id is not None else None
            ),
            metadata={
                "chat_id": str(chat_id),
                "bridge_mode": "historical-external-process",
            },
        )

    def health_check(self) -> HealthReport:
        return self.plugin_bridge.health("telegram", probe=self.transport)

    @staticmethod
    def _display_name(user: Mapping[str, Any]) -> str | None:
        parts = [
            value.strip()
            for value in (user.get("first_name"), user.get("last_name"))
            if isinstance(value, str) and value.strip()
        ]
        if parts:
            return " ".join(parts)
        username = user.get("username")
        return str(username) if username else None
