"""Versioned, channel-neutral inbound message contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from .artifact import Artifact, ArtifactKind


MESSAGE_SCHEMA_VERSION = "message.v1"


class MessageType(str, Enum):
    """Message shapes supported by the first contract version."""

    TEXT = "text"
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"
    EVENT = "event"
    MIXED = "mixed"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_utc_timestamp(value: str) -> None:
    _require_text(value, "timestamp")
    if not value.endswith("Z"):
        raise ValueError("timestamp must be an RFC 3339 UTC value ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("timestamp must be a valid RFC 3339 UTC value") from exc


@dataclass(frozen=True, slots=True)
class ChannelRef:
    """Provider routing identity without credentials."""

    type: str
    instance_id: str
    message_id: str
    thread_id: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.type, "channel.type")
        _require_text(self.instance_id, "channel.instance_id")
        _require_text(self.message_id, "channel.message_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "instance_id": self.instance_id,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "tenant_id": self.tenant_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ChannelRef":
        if not isinstance(data, Mapping):
            raise TypeError("channel must be a mapping")
        return cls(
            type=data["type"],
            instance_id=data["instance_id"],
            message_id=data["message_id"],
            thread_id=data.get("thread_id"),
            tenant_id=data.get("tenant_id"),
        )


@dataclass(frozen=True, slots=True)
class UserRef:
    """Platform and provider identity pair."""

    id: str
    external_id: str
    display_name: str | None = None
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "user.id")
        _require_text(self.external_id, "user.external_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "display_name": self.display_name,
            "tenant_id": self.tenant_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UserRef":
        if not isinstance(data, Mapping):
            raise TypeError("user must be a mapping")
        return cls(
            id=data["id"],
            external_id=data["external_id"],
            display_name=data.get("display_name"),
            tenant_id=data.get("tenant_id"),
        )


@dataclass(frozen=True, slots=True)
class MessageContent:
    """User-visible text and/or a namespaced channel event."""

    text: str | None = None
    event: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.text is not None and not isinstance(self.text, str):
            raise TypeError("content.text must be a string or None")
        if self.event is not None:
            if not isinstance(self.event, Mapping):
                raise TypeError("content.event must be a mapping or None")
            name = self.event.get("name")
            _require_text(name, "content.event.name")
            payload = self.event.get("payload", {})
            if not isinstance(payload, Mapping):
                raise TypeError("content.event.payload must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "event": dict(self.event) if self.event is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MessageContent":
        if not isinstance(data, Mapping):
            raise TypeError("content must be a mapping")
        return cls(text=data.get("text"), event=data.get("event"))


@dataclass(frozen=True, slots=True)
class ReplyTo:
    """Reference to an earlier normalized or provider message."""

    message_id: str
    provider_message_id: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.message_id, "reply_to.message_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "provider_message_id": self.provider_message_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ReplyTo":
        if not isinstance(data, Mapping):
            raise TypeError("reply_to must be a mapping")
        return cls(
            message_id=data["message_id"],
            provider_message_id=data.get("provider_message_id"),
        )


@dataclass(frozen=True, slots=True)
class MessageEvent:
    """Canonical event produced by every inbound channel adapter.

    ``version`` is serialized as ``schema_version`` to match the wire contract
    in ``docs/MESSAGE_MODEL_DESIGN.md``.
    """

    id: str
    version: str
    trace_id: str
    channel: ChannelRef
    user: UserRef
    session_id: str
    conversation_id: str
    timestamp: str
    type: MessageType
    content: MessageContent
    attachments: Sequence[Artifact] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    reply_to: ReplyTo | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "version", "trace_id", "session_id", "conversation_id"):
            _require_text(getattr(self, field_name), field_name)
        if self.version != MESSAGE_SCHEMA_VERSION:
            raise ValueError(f"unsupported message version: {self.version}")
        _validate_utc_timestamp(self.timestamp)

        if not isinstance(self.channel, ChannelRef):
            raise TypeError("channel must be a ChannelRef")
        if not isinstance(self.user, UserRef):
            raise TypeError("user must be a UserRef")
        if isinstance(self.type, str):
            try:
                object.__setattr__(self, "type", MessageType(self.type))
            except ValueError as exc:
                raise ValueError(f"unsupported message type: {self.type}") from exc
        elif not isinstance(self.type, MessageType):
            raise TypeError("type must be a MessageType or supported string")
        if not isinstance(self.content, MessageContent):
            raise TypeError("content must be a MessageContent")
        if isinstance(self.attachments, (str, bytes)):
            raise TypeError("attachments must be a sequence of Artifact objects")
        normalized_attachments = tuple(self.attachments)
        if not all(isinstance(item, Artifact) for item in normalized_attachments):
            raise TypeError("attachments must contain only Artifact objects")
        object.__setattr__(self, "attachments", normalized_attachments)
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        if self.reply_to is not None and not isinstance(self.reply_to, ReplyTo):
            raise TypeError("reply_to must be a ReplyTo or None")

        self._validate_content_shape()

    @property
    def schema_version(self) -> str:
        """Alias used by the wire-level design document."""

        return self.version

    def _validate_content_shape(self) -> None:
        if self.type is MessageType.TEXT and not self.content.text:
            raise ValueError("text messages require content.text")
        if self.type is MessageType.EVENT and self.content.event is None:
            raise ValueError("event messages require content.event")
        required_kind = {
            MessageType.FILE: ArtifactKind.FILE,
            MessageType.IMAGE: ArtifactKind.IMAGE,
            MessageType.AUDIO: ArtifactKind.AUDIO,
        }.get(self.type)
        if required_kind is not None and not any(
            item.kind is required_kind for item in self.attachments
        ):
            raise ValueError(f"{self.type.value} messages require a matching attachment")
        if self.type is MessageType.MIXED and not (self.content.text or self.attachments):
            raise ValueError("mixed messages require text or attachments")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable wire representation."""

        return {
            "schema_version": self.version,
            "id": self.id,
            "trace_id": self.trace_id,
            "channel": self.channel.to_dict(),
            "user": self.user.to_dict(),
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "content": self.content.to_dict(),
            "attachments": [item.to_dict() for item in self.attachments],
            "metadata": dict(self.metadata),
            "reply_to": self.reply_to.to_dict() if self.reply_to is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MessageEvent":
        """Build and validate a MessageEvent from decoded JSON."""

        if not isinstance(data, Mapping):
            raise TypeError("message event data must be a mapping")
        version = data.get("schema_version", data.get("version"))
        if "schema_version" in data and "version" in data:
            if data["schema_version"] != data["version"]:
                raise ValueError("schema_version and version must match")
        return cls(
            id=data["id"],
            version=version,
            trace_id=data["trace_id"],
            channel=ChannelRef.from_dict(data["channel"]),
            user=UserRef.from_dict(data["user"]),
            session_id=data["session_id"],
            conversation_id=data["conversation_id"],
            timestamp=data["timestamp"],
            type=data["type"],
            content=MessageContent.from_dict(data["content"]),
            attachments=tuple(Artifact.from_dict(item) for item in data.get("attachments", [])),
            metadata=data.get("metadata", {}),
            reply_to=(
                ReplyTo.from_dict(data["reply_to"])
                if data.get("reply_to") is not None
                else None
            ),
        )
