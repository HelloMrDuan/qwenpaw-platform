from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
from tests._qwenpaw_v2_1_support import install_qwenpaw_v2_1_stubs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer-channel-plugin"


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        "wechat_customer_native_channel_test_plugin",
        PLUGIN_ROOT / "plugin.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load WeChat Customer Plugin")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(message_id="msg-1", external_userid="ext-1", open_kfid="kf-1"):
    return {
        "msgid": message_id,
        "msgtype": "text",
        "origin": 3,
        "external_userid": external_userid,
        "open_kfid": open_kfid,
        "text": {"content": "离线微信客服消息"},
        "gateway_delivery": {
            "delivery_id": f"delivery-{message_id}",
            "cursor_committed": True,
            "db_claimed": True,
        },
    }


class _Facade:
    def __init__(self):
        self.external_api_verified = False
        self.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail="offline Gateway ready",
        )
        self.events = []
        self.sent = []
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def check(self, descriptor):
        del descriptor
        return self.snapshot

    def receive_event(self):
        return self.events.pop(0) if self.events else None

    def send_text(self, external_userid, open_kfid, text, reply_to):
        self.sent.append((external_userid, open_kfid, text, reply_to))
        return "provider-reply-1"


class WeChatCustomerBaseChannelTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_channel = install_qwenpaw_v2_1_stubs()
        cls.plugin_module = _load_plugin()
        cls.channel_class = cls.plugin_module.plugin.load_channel_class()

    def _channel(self, facade=None, **overrides):
        values = {
            "enabled": True,
            "corp_id": "corp-test",
            "app_secret": "secret-test",
            "callback_token": "token-test",
            "encoding_aes_key": "aes-test",
            "open_kfid": "kf-1",
            "gateway_url": "http://127.0.0.1:8798",
            "bot_prefix": "",
        }
        values.update(overrides)
        facade = facade or _Facade()
        original = self.channel_class.facade_factory
        self.channel_class.facade_factory = staticmethod(lambda url: facade)
        try:
            channel = self.channel_class.from_config(lambda request: None, SimpleNamespace(**values))
        finally:
            self.channel_class.facade_factory = original
        return channel, facade

    async def test_official_contract_session_isolation_and_response(self):
        self.assertTrue(issubclass(self.channel_class, self.base_channel))
        self.assertEqual(self.channel_class.channel, "wechat_customer")
        self.assertFalse(self.channel_class.streaming_enabled)
        channel, facade = self._channel()
        queued = []
        channel.set_enqueue(queued.append)

        message = channel.submit_gateway_event(_event())
        self.assertEqual(len(queued), 1)
        self.assertNotIn("cursor", queued[0]["meta"])
        self.assertNotIn("next_cursor", queued[0]["meta"])
        request = channel.build_agent_request_from_native(queued[0])
        self.assertEqual(request.channel, "wechat_customer")
        self.assertEqual(request.session_id, message.session_id)
        self.assertEqual(
            request.session_id,
            channel.resolve_session_id(
                "ext-1", {"open_kfid": "kf-1", "external_userid": "ext-1"}
            ),
        )
        self.assertNotEqual(
            request.session_id,
            channel.resolve_session_id(
                "ext-2", {"open_kfid": "kf-1", "external_userid": "ext-2"}
            ),
        )
        self.assertNotEqual(
            request.session_id,
            channel.resolve_session_id(
                "ext-1", {"open_kfid": "kf-2", "external_userid": "ext-1"}
            ),
        )

        await channel.send("ext-1", "最终聚合回复", queued[0]["meta"])
        self.assertEqual(
            facade.sent,
            [("ext-1", "kf-1", "最终聚合回复", "msg-1")],
        )
        self.assertEqual(
            channel.last_delivery_receipt.provider_message_id,
            "provider-reply-1",
        )

    async def test_health_states_do_not_claim_connected_without_verification(self):
        incomplete, _ = self._channel(app_secret="")
        self.assertEqual((await incomplete.health_check())["code"], "CONFIG_REQUIRED")

        channel, facade = self._channel()
        self.assertEqual((await channel.health_check())["code"], "PLUGIN_READY")
        await channel.start()
        self.assertEqual((await channel.health_check())["code"], "EXTERNAL_API_UNVERIFIED")
        facade.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.STOPPED,
            reachable=False,
            detail="offline Gateway stopped",
        )
        self.assertEqual((await channel.health_check())["code"], "GATEWAY_NOT_RUNNING")
        facade.snapshot = ExternalServiceSnapshot(
            state=ExternalServiceState.RUNNING,
            reachable=True,
            detail="offline Gateway and API verified",
        )
        facade.external_api_verified = True
        ready = await channel.health_check()
        self.assertEqual(ready["code"], "GATEWAY_READY")
        self.assertEqual(ready["status"], "healthy")
        await channel.stop()


if __name__ == "__main__":
    unittest.main()
