"""Adapter-preserving bridge used by the native QwenPaw Channel."""

from __future__ import annotations

from typing import Any, Mapping

try:
    from .adapter.wechat_customer.runtime import WeChatCustomerRuntimeAdapter
except ImportError:  # Source-repository execution.
    from adapters.wechat_customer.runtime import WeChatCustomerRuntimeAdapter

from .gateway_facade import GatewayFacade


class _ChannelHealthBoundary:
    """Placeholder PluginBridge; Channel health is mapped separately."""

    def health(self, *args: Any, **kwargs: Any):
        raise RuntimeError("Channel health must use the Gateway facade probe")


class WeChatCustomerGatewayBridge:
    """Reuse the existing Adapter without acquiring Gateway state ownership."""

    def __init__(self, facade: GatewayFacade, *, instance_id: str) -> None:
        if not isinstance(facade, GatewayFacade):
            raise TypeError("facade must implement the GatewayFacade contract")
        self.facade = facade
        self.adapter = WeChatCustomerRuntimeAdapter(
            _ChannelHealthBoundary(),
            facade,
            instance_id=instance_id,
        )

    def receive_message(self):
        return self.adapter.receive_message()

    def parse_message(self, payload: Mapping[str, Any]):
        return self.adapter.parse_message(payload)

    def send_response(self, message, response: str):
        return self.adapter.send_response(message, response)

    @staticmethod
    def session_id(open_kfid: str, external_userid: str) -> str:
        identity = WeChatCustomerRuntimeAdapter._session_identity(
            open_kfid,
            external_userid,
        )
        return f"ses_wechat_customer_{identity}"
