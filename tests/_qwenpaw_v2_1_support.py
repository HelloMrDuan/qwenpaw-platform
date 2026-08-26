"""Minimal QwenPaw v2.1.0 contract stubs for offline Plugin tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import sys
from types import ModuleType, SimpleNamespace
from typing import Any


def install_qwenpaw_v2_1_stubs() -> type:
    """Install only the official types required to import a custom Channel."""

    existing = sys.modules.get("qwenpaw.app.channels.base")
    if existing is not None and hasattr(existing, "BaseChannel"):
        return existing.BaseChannel

    qwenpaw = ModuleType("qwenpaw")
    app = ModuleType("qwenpaw.app")
    channels = ModuleType("qwenpaw.app.channels")
    base = ModuleType("qwenpaw.app.channels.base")
    renderer = ModuleType("qwenpaw.app.channels.renderer")
    schemas = ModuleType("qwenpaw.schemas")

    class ChannelDisplayConfig:
        @classmethod
        def from_config(cls, config):
            del config
            return cls()

    class ContentType(str, Enum):
        TEXT = "text"

    @dataclass
    class TextContent:
        type: ContentType
        text: str

    class BaseChannel:
        channel: str
        uses_manager_queue = True
        streaming_enabled = False

        def __init__(
            self,
            process,
            on_reply_sent=None,
            display_config=None,
            dm_policy="open",
            group_policy="open",
            allow_from=None,
            deny_message="",
            require_mention=False,
            no_text_debounce=True,
            streaming_enabled=False,
            access_control_dm=False,
            access_control_group=False,
        ):
            self._process = process
            self._on_reply_sent = on_reply_sent
            self._display_config = display_config or ChannelDisplayConfig()
            self._enqueue = None
            self.streaming_enabled = streaming_enabled
            self.dm_policy = dm_policy
            self.group_policy = group_policy
            self.allow_from = set(allow_from or [])
            self.deny_message = deny_message
            self.require_mention = require_mention
            self._no_text_debounce = no_text_debounce
            self.access_control_dm = access_control_dm
            self.access_control_group = access_control_group

        def set_enqueue(self, callback):
            self._enqueue = callback

        def build_agent_request_from_user_content(
            self,
            channel_id,
            sender_id,
            session_id,
            content_parts,
            channel_meta=None,
        ):
            return SimpleNamespace(
                channel=channel_id,
                user_id=sender_id,
                session_id=session_id,
                content_parts=content_parts,
                channel_meta=channel_meta or {},
            )

    base.BaseChannel = BaseChannel
    base.OnReplySent = Any
    base.ProcessHandler = Any
    renderer.ChannelDisplayConfig = ChannelDisplayConfig
    schemas.ContentType = ContentType
    schemas.TextContent = TextContent

    qwenpaw.app = app
    qwenpaw.schemas = schemas
    app.channels = channels
    channels.base = base
    channels.renderer = renderer
    sys.modules.update(
        {
            "qwenpaw": qwenpaw,
            "qwenpaw.app": app,
            "qwenpaw.app.channels": channels,
            "qwenpaw.app.channels.base": base,
            "qwenpaw.app.channels.renderer": renderer,
            "qwenpaw.schemas": schemas,
        }
    )
    return BaseChannel
