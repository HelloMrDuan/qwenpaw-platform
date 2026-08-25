"""Extension-layer Console implementation of the ChannelAdapter contract."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping, Sequence, TextIO
from uuid import uuid4

from core.contracts import (
    Artifact,
    ChannelRef,
    DeliveryReceipt,
    DeliveryStatus,
    MESSAGE_SCHEMA_VERSION,
    MessageContent,
    MessageEvent,
    MessageType,
    StreamEvent,
    UserRef,
)
from core.renderers import ConsoleRenderer

from .renderer import ConsoleOutputWriter


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


class ConsoleChannelAdapter:
    """Normalize Console text and write rendered events to a text stream.

    The adapter performs no model invocation and has no QwenPaw Runtime
    dependency. A text stream can be injected for deterministic offline tests.
    """

    channel_type = "console"

    def __init__(
        self,
        *,
        output: TextIO | None = None,
        instance_id: str = "console-local",
    ) -> None:
        self.instance_id = _require_text(instance_id, "instance_id")
        self.renderer = ConsoleRenderer()
        self.writer = ConsoleOutputWriter(output)
        self._delivery_counter = 0
        self._lock = RLock()

    def parse_message(self, payload: Mapping[str, Any]) -> MessageEvent:
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        text = _require_text(payload.get("text"), "payload.text")
        user_external_id = _require_text(
            payload.get("user_id", "console-user"), "payload.user_id"
        )
        message_id = _require_text(
            payload.get("message_id", f"console-{uuid4().hex}"),
            "payload.message_id",
        )
        session_id = _require_text(
            payload.get("session_id", f"ses_console_{user_external_id}"),
            "payload.session_id",
        )
        conversation_id = _require_text(
            payload.get("conversation_id", f"conv_console_{user_external_id}"),
            "payload.conversation_id",
        )
        trace_id = _require_text(
            payload.get("trace_id", f"trc_{message_id}"), "payload.trace_id"
        )
        timestamp = _require_text(
            payload.get("timestamp", _utc_now()), "payload.timestamp"
        )
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise TypeError("payload.metadata must be a mapping")

        return MessageEvent(
            id=f"msg_{message_id}",
            version=MESSAGE_SCHEMA_VERSION,
            trace_id=trace_id,
            channel=ChannelRef(
                type=self.channel_type,
                instance_id=self.instance_id,
                message_id=message_id,
            ),
            user=UserRef(
                id=_require_text(
                    payload.get("platform_user_id", user_external_id),
                    "payload.platform_user_id",
                ),
                external_id=user_external_id,
                display_name=payload.get("display_name"),
            ),
            session_id=session_id,
            conversation_id=conversation_id,
            timestamp=timestamp,
            type=MessageType.TEXT,
            content=MessageContent(text=text),
            metadata={**dict(metadata), "input_mode": "console"},
        )

    async def send_message(
        self,
        session_id: str,
        message: str,
        *,
        artifacts: Sequence[Artifact] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DeliveryReceipt:
        session_id = _require_text(session_id, "session_id")
        message = _require_text(message, "message")
        if isinstance(artifacts, (str, bytes)):
            raise TypeError("artifacts must be a sequence of Artifact objects")
        normalized_artifacts = tuple(artifacts)
        if not all(isinstance(item, Artifact) for item in normalized_artifacts):
            raise TypeError("artifacts must contain only Artifact objects")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping or None")
        try:
            self.writer.write_message(message)
            for artifact in normalized_artifacts:
                self.writer.write_artifact(artifact)
        except OSError as exc:
            return self._receipt(
                session_id,
                DeliveryStatus.FAILED,
                metadata={"error": type(exc).__name__},
            )
        return self._receipt(
            session_id,
            DeliveryStatus.SENT,
            metadata={
                "artifact_ids": [item.id for item in normalized_artifacts],
                **dict(metadata or {}),
            },
        )

    async def send_stream_event(
        self, event: StreamEvent
    ) -> DeliveryReceipt | None:
        if not isinstance(event, StreamEvent):
            raise TypeError("event must be a StreamEvent")
        outputs = self.renderer.render(event)
        if not outputs:
            return None
        try:
            for output in outputs:
                self.writer.write(output)
        except OSError as exc:
            return self._receipt(
                event.session_id,
                DeliveryStatus.FAILED,
                metadata={
                    "event_id": event.event_id,
                    "error": type(exc).__name__,
                },
            )
        return self._receipt(
            event.session_id,
            DeliveryStatus.SENT,
            metadata={
                "event_id": event.event_id,
                "event": event.event.value,
                "rendered_output_ids": [item.id for item in outputs],
            },
        )

    def _receipt(
        self,
        session_id: str,
        status: DeliveryStatus,
        *,
        metadata: Mapping[str, Any],
    ) -> DeliveryReceipt:
        with self._lock:
            self._delivery_counter += 1
            delivery_id = f"console-delivery-{self._delivery_counter:06d}"
        return DeliveryReceipt(
            delivery_id=delivery_id,
            channel=self.channel_type,
            session_id=session_id,
            status=status,
            provider_message_id=delivery_id,
            metadata=dict(metadata),
        )
