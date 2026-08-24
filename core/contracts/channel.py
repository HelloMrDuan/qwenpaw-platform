"""Structural contract for future channel adapters.

No real provider connection or transport implementation belongs in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .artifact import Artifact
from .message import MessageEvent
from .streaming import StreamEvent


class DeliveryStatus(str, Enum):
    """Provider-neutral outbound delivery status."""

    ACCEPTED = "accepted"
    SENT = "sent"
    FAILED = "failed"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    """Safe receipt returned by an outbound channel operation."""

    delivery_id: str
    channel: str
    session_id: str
    status: DeliveryStatus
    provider_message_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.delivery_id, "delivery_id")
        _require_text(self.channel, "channel")
        _require_text(self.session_id, "session_id")
        if isinstance(self.status, str):
            try:
                object.__setattr__(self, "status", DeliveryStatus(self.status))
            except ValueError as exc:
                raise ValueError(f"unsupported delivery status: {self.status}") from exc
        elif not isinstance(self.status, DeliveryStatus):
            raise TypeError("status must be a DeliveryStatus or supported string")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "channel": self.channel,
            "session_id": self.session_id,
            "status": self.status.value,
            "provider_message_id": self.provider_message_id,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class ChannelAdapter(Protocol):
    """Minimum interface every future channel adapter must satisfy.

    Implementations may use webhooks, polling, WebSockets, or provider SDKs.
    The contract intentionally says nothing about those runtime choices.
    """

    channel_type: str

    def parse_message(self, payload: Mapping[str, Any]) -> MessageEvent:
        """Validate and normalize one provider payload."""
        ...

    async def send_message(
        self,
        session_id: str,
        message: str,
        *,
        artifacts: Sequence[Artifact] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DeliveryReceipt:
        """Send a complete message using provider-specific rendering."""
        ...

    async def send_stream_event(self, event: StreamEvent) -> DeliveryReceipt | None:
        """Render one ordered event, or buffer it until delivery is possible."""
        ...
