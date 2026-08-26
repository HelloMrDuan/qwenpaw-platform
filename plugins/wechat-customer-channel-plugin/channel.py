"""QwenPaw v2.1.0 native Channel for the external WeChat Customer Gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from qwenpaw.app.channels.base import BaseChannel, OnReplySent, ProcessHandler
from qwenpaw.app.channels.renderer import ChannelDisplayConfig
from qwenpaw.schemas import ContentType, TextContent

try:
    from .core.contracts import MessageEvent
    from .core.extensions.runtime import ExternalServiceState
except ImportError:  # Source-repository execution.
    from core.contracts import MessageEvent
    from core.extensions.runtime import ExternalServiceState

from .gateway_bridge import WeChatCustomerGatewayBridge
from .gateway_facade import GatewayFacade, HttpGatewayFacade


REQUIRED_CONFIG_FIELDS = (
    "corp_id",
    "app_secret",
    "callback_token",
    "encoding_aes_key",
    "open_kfid",
)


class WeChatCustomerChannel(BaseChannel):
    """Thin QwenPaw Channel; the external Gateway remains state owner."""

    channel = "wechat_customer"
    uses_manager_queue = True
    streaming_enabled = False
    facade_factory = HttpGatewayFacade

    def __init__(
        self,
        process: ProcessHandler,
        *,
        enabled: bool,
        open_kfid: str,
        gateway_url: str,
        configured_fields: frozenset[str],
        bot_prefix: str = "",
        facade: GatewayFacade | None = None,
        workspace_dir: Path | None = None,
        on_reply_sent: OnReplySent = None,
        display_config: ChannelDisplayConfig | None = None,
        no_text_debounce: bool = True,
        dm_policy: str = "open",
        group_policy: str = "open",
        allow_from: Optional[list] = None,
        deny_message: str = "",
        require_mention: bool = False,
        access_control_dm: bool = False,
        access_control_group: bool = False,
    ) -> None:
        super().__init__(
            process,
            on_reply_sent=on_reply_sent,
            display_config=display_config,
            no_text_debounce=no_text_debounce,
            dm_policy=dm_policy,
            group_policy=group_policy,
            allow_from=allow_from,
            deny_message=deny_message,
            require_mention=require_mention,
            streaming_enabled=False,
            access_control_dm=access_control_dm,
            access_control_group=access_control_group,
        )
        self.enabled = bool(enabled)
        self.bot_prefix = bot_prefix or ""
        self.open_kfid = str(open_kfid or "").strip()
        self.gateway_url = str(gateway_url or "").strip().rstrip("/")
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self._configured_fields = frozenset(configured_fields)
        self._facade = facade or self.facade_factory(self.gateway_url)
        self._bridge = WeChatCustomerGatewayBridge(
            self._facade,
            instance_id="wechat-customer-qwenpaw-native",
        )
        self._poll_task: asyncio.Task[None] | None = None
        self._started = False
        self._last_delivery_receipt = None

    @classmethod
    def from_config(
        cls,
        process: ProcessHandler,
        config: Any,
        on_reply_sent: OnReplySent = None,
        display_config: ChannelDisplayConfig | None = None,
        no_text_debounce: bool = True,
        workspace_dir: Path | None = None,
    ) -> "WeChatCustomerChannel":
        """Create from QwenPaw's plugin-channel ``SimpleNamespace`` config."""

        present = frozenset(
            name
            for name in REQUIRED_CONFIG_FIELDS
            if str(getattr(config, name, "") or "").strip()
        )
        return cls(
            process=process,
            enabled=bool(getattr(config, "enabled", False)),
            open_kfid=getattr(config, "open_kfid", ""),
            gateway_url=(
                getattr(config, "gateway_url", "")
                or "http://127.0.0.1:8798"
            ),
            configured_fields=present,
            bot_prefix=getattr(config, "bot_prefix", ""),
            workspace_dir=workspace_dir,
            on_reply_sent=on_reply_sent,
            display_config=display_config
            or ChannelDisplayConfig.from_config(config),
            no_text_debounce=no_text_debounce,
            dm_policy=getattr(config, "dm_policy", "open"),
            group_policy=getattr(config, "group_policy", "open"),
            allow_from=getattr(config, "allow_from", []),
            deny_message=getattr(config, "deny_message", ""),
            require_mention=bool(getattr(config, "require_mention", False)),
            access_control_dm=bool(
                getattr(config, "access_control_dm", False)
            ),
            access_control_group=bool(
                getattr(config, "access_control_group", False)
            ),
        )

    @property
    def last_delivery_receipt(self):
        return self._last_delivery_receipt

    def resolve_session_id(
        self,
        sender_id: str,
        channel_meta: Optional[dict[str, Any]] = None,
    ) -> str:
        meta = channel_meta or {}
        open_kfid = str(meta.get("open_kfid") or self.open_kfid).strip()
        external_userid = str(meta.get("external_userid") or sender_id).strip()
        if not open_kfid or not external_userid:
            raise ValueError("open_kfid and external_userid are required")
        return self._bridge.session_id(open_kfid, external_userid)

    def build_agent_request_from_native(self, native_payload: Any):
        if not isinstance(native_payload, Mapping):
            raise TypeError("native payload must be a mapping")
        sender_id = str(native_payload.get("sender_id") or "").strip()
        content_parts = list(native_payload.get("content_parts") or [])
        meta = dict(native_payload.get("meta") or {})
        session_id = self.resolve_session_id(sender_id, meta)
        request = self.build_agent_request_from_user_content(
            channel_id=self.channel,
            sender_id=sender_id,
            session_id=session_id,
            content_parts=content_parts,
            channel_meta=meta,
        )
        request.user_id = sender_id
        request.channel_meta = meta
        return request

    def submit_gateway_event(self, payload: Mapping[str, Any]) -> MessageEvent:
        """Accept one already cursor-committed and DB-claimed Gateway event."""

        message = self._bridge.parse_message(payload)
        event_open_kfid = str(message.metadata["open_kfid"])
        if self.open_kfid and event_open_kfid != self.open_kfid:
            raise ValueError("Gateway event open_kfid does not match Channel config")
        native = {
            "channel_id": self.channel,
            "sender_id": message.user.external_id,
            "acl_sender_id": message.user.external_id,
            "content_parts": [
                TextContent(type=ContentType.TEXT, text=message.content.text)
            ],
            "meta": {
                "message_event": message,
                "message_id": message.channel.message_id,
                "external_userid": message.metadata["external_userid"],
                "open_kfid": event_open_kfid,
                "session_id": message.session_id,
                "state_owner": "gateway",
                "cursor_committed": True,
                "db_claimed": True,
            },
        }
        if self._enqueue is None:
            raise RuntimeError("QwenPaw ChannelManager queue is not attached")
        self._enqueue(native)
        return message

    async def start(self) -> None:
        if self._started or not self.enabled:
            return
        if not self._configuration_complete:
            return
        self._facade.start()
        self._started = True
        self._poll_task = asyncio.create_task(self._poll_gateway())

    async def stop(self) -> None:
        self._started = False
        task = self._poll_task
        self._poll_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._facade.stop()

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        del to_handle
        message = (meta or {}).get("message_event")
        if not isinstance(message, MessageEvent):
            raise ValueError("Gateway-owned MessageEvent is required for reply")
        self._last_delivery_receipt = await asyncio.to_thread(
            self._bridge.send_response,
            message,
            str(text or ""),
        )

    async def health_check(self) -> dict[str, Any]:
        if not self._configuration_complete:
            return self._health(
                "unhealthy",
                "CONFIG_REQUIRED",
                "Required WeChat Customer configuration is incomplete",
            )
        if not self._started:
            return self._health(
                "degraded",
                "PLUGIN_READY",
                "Channel is configured but not started",
            )
        snapshot = await asyncio.to_thread(self._facade.check, None)
        if (
            snapshot.state is not ExternalServiceState.RUNNING
            or not snapshot.reachable
        ):
            return self._health(
                "unhealthy",
                "GATEWAY_NOT_RUNNING",
                snapshot.detail,
            )
        if not bool(getattr(self._facade, "external_api_verified", False)):
            return self._health(
                "degraded",
                "EXTERNAL_API_UNVERIFIED",
                "Gateway is reachable; external WeChat Customer API is unverified",
            )
        return self._health("healthy", "GATEWAY_READY", snapshot.detail)

    @property
    def _configuration_complete(self) -> bool:
        return set(REQUIRED_CONFIG_FIELDS).issubset(self._configured_fields)

    async def _poll_gateway(self) -> None:
        while self._started:
            try:
                event = await asyncio.to_thread(self._facade.receive_event)
                if event is not None:
                    self.submit_gateway_event(event)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(0.5)

    def _health(self, status: str, code: str, detail: str) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "status": status,
            "code": code,
            "detail": detail,
            "gateway_url": self.gateway_url,
            "state_owner": "gateway",
            "external_api_verified": code == "GATEWAY_READY",
        }
