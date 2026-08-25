"""Safe facade from recovered WeChat Customer Gateway events to MessageEvent.

The historical Gateway remains the exclusive owner of provider credentials,
cursor persistence, SQLite state, message deduplication, and delivery calls.
This module only accepts a normalized, post-commit event from an injected
transport.  It never imports or starts the historical Gateway.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
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
_DELIVERY_FIELDS = frozenset({"delivery_id", "cursor_committed", "db_claimed"})
_FORBIDDEN_CURSOR_FIELDS = frozenset({"cursor", "next_cursor"})


@runtime_checkable
class WeChatCustomerGatewayTransport(ExternalServiceProbe, Protocol):
    """Injected boundary for a separately supervised historical Gateway."""

    def receive_event(self) -> Mapping[str, Any] | None:
        """Return one normalized event after Gateway state is durable."""
        ...

    def send_text(
        self,
        external_userid: str,
        open_kfid: str,
        text: str,
        reply_to: str,
    ) -> str | None:
        """Ask the Gateway to deliver text and return its provider message id."""
        ...


class WeChatCustomerRuntimeError(ValueError):
    """Raised when a Gateway event cannot cross the Extension boundary."""


class WeChatCustomerRuntimeAdapter:
    """Normalize post-commit Gateway text events without touching Gateway state."""

    channel_type = "wechat-customer"

    def __init__(
        self,
        plugin_bridge: PluginRuntimeBridge,
        transport: WeChatCustomerGatewayTransport,
        *,
        instance_id: str = "wechat-customer-recovered",
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(transport, WeChatCustomerGatewayTransport):
            raise TypeError("transport must implement receive_event/send_text/check")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError("instance_id must be non-empty text")
        self.plugin_bridge = plugin_bridge
        self.transport = transport
        self.instance_id = instance_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def receive_message(self) -> MessageEvent | None:
        payload = self.transport.receive_event()
        if payload is None:
            return None
        return self.parse_message(payload)

    def parse_message(self, payload: Mapping[str, Any]) -> MessageEvent:
        if not isinstance(payload, Mapping):
            raise TypeError("WeChat Customer Gateway event must be a mapping")
        forbidden = _FORBIDDEN_CURSOR_FIELDS.intersection(payload)
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise WeChatCustomerRuntimeError(
                f"Gateway cursor values must not cross the Extension boundary: {names}"
            )

        delivery = self._validated_delivery(payload.get("gateway_delivery"))
        message_id = self._required_text(payload.get("msgid"), "msgid")
        external_userid = self._required_text(
            payload.get("external_userid"), "external_userid"
        )
        open_kfid = self._required_text(payload.get("open_kfid"), "open_kfid")
        if payload.get("origin") != 3:
            raise WeChatCustomerRuntimeError("only origin=3 customer messages are supported")
        if payload.get("msgtype") != "text":
            raise WeChatCustomerRuntimeError("historical Gateway bridge supports text only")
        text_block = payload.get("text")
        if not isinstance(text_block, Mapping):
            raise WeChatCustomerRuntimeError("text payload is required")
        content = self._required_text(text_block.get("content"), "text.content")

        identity = self._session_identity(open_kfid, external_userid)
        timestamp = self._timestamp()
        return MessageEvent(
            id=f"msg_wechat_customer_{message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=f"trc_wechat_customer_{message_id}",
            channel=ChannelRef(
                type=self.channel_type,
                instance_id=self.instance_id,
                message_id=message_id,
                thread_id=f"customer_{identity}",
                tenant_id=open_kfid,
            ),
            user=UserRef(
                id=f"usr_wechat_customer_{identity}",
                external_id=external_userid,
                tenant_id=open_kfid,
            ),
            session_id=f"ses_wechat_customer_{identity}",
            conversation_id=f"conv_wechat_customer_{identity}",
            timestamp=timestamp,
            type=MessageType.TEXT,
            content=MessageContent(text=content),
            metadata={
                "provider": "wechat-customer",
                "provider_message_id": message_id,
                "external_userid": external_userid,
                "open_kfid": open_kfid,
                "origin": 3,
                "msgtype": "text",
                "gateway_delivery_id": delivery["delivery_id"],
                "cursor_committed": True,
                "db_claimed": True,
                "state_owner": "gateway",
                "session_mapping": "sha256(open_kfid\\0external_userid):24",
                "timestamp_source": "extension_received_at",
                "bridge_mode": "historical-external-gateway",
            },
        )

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        if not isinstance(message, MessageEvent):
            raise TypeError("message must be a MessageEvent")
        if message.channel.type != self.channel_type:
            raise WeChatCustomerRuntimeError(
                "MessageEvent is not from WeChat Customer"
            )
        response = self._required_text(response, "response")
        external_userid = self._required_text(
            message.metadata.get("external_userid"), "metadata.external_userid"
        )
        open_kfid = self._required_text(
            message.metadata.get("open_kfid"), "metadata.open_kfid"
        )
        provider_message_id = self.transport.send_text(
            external_userid,
            open_kfid,
            response,
            message.channel.message_id,
        )
        return DeliveryReceipt(
            delivery_id=f"delivery_wechat_customer_{message.channel.message_id}",
            channel=self.channel_type,
            session_id=message.session_id,
            status=DeliveryStatus.SENT,
            provider_message_id=(
                str(provider_message_id) if provider_message_id is not None else None
            ),
            metadata={
                "external_userid": external_userid,
                "open_kfid": open_kfid,
                "reply_to": message.channel.message_id,
                "state_owner": "gateway",
                "bridge_mode": "historical-external-gateway",
            },
        )

    def health_check(self) -> HealthReport:
        """Probe the external Gateway and synchronize local lifecycle state."""

        return self.plugin_bridge.health("wechat-customer", probe=self.transport)

    @staticmethod
    def _validated_delivery(value: object) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise WeChatCustomerRuntimeError("gateway_delivery is required")
        unexpected = set(value).difference(_DELIVERY_FIELDS)
        if unexpected:
            names = ", ".join(sorted(str(item) for item in unexpected))
            raise WeChatCustomerRuntimeError(
                f"gateway_delivery contains unsupported state fields: {names}"
            )
        delivery_id = value.get("delivery_id")
        if not isinstance(delivery_id, str) or not delivery_id.strip():
            raise WeChatCustomerRuntimeError("gateway_delivery.delivery_id is required")
        if value.get("cursor_committed") is not True:
            raise WeChatCustomerRuntimeError(
                "Gateway must persist its cursor before Extension delivery"
            )
        if value.get("db_claimed") is not True:
            raise WeChatCustomerRuntimeError(
                "Gateway must claim the message in its database before delivery"
            )
        return value

    @staticmethod
    def _required_text(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise WeChatCustomerRuntimeError(f"{field_name} is required")
        return value.strip()

    @staticmethod
    def _session_identity(open_kfid: str, external_userid: str) -> str:
        source = f"{open_kfid}\0{external_userid}".encode("utf-8")
        return hashlib.sha256(source).hexdigest()[:24]

    def _timestamp(self) -> str:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise WeChatCustomerRuntimeError(
                "clock must return a timezone-aware datetime"
            )
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
