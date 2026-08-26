from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.build_extension import build_qwenpaw_plugins
from tests._qwenpaw_v2_1_support import install_qwenpaw_v2_1_stubs


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPOSITORY_ROOT / "plugins" / "wechat-customer-channel-plugin"
BUILTIN_V2_1_CHANNEL_KEYS = {
    "imessage", "discord", "dingtalk", "feishu", "qq", "telegram",
    "mattermost", "mqtt", "console", "matrix", "voice", "sip", "wecom",
    "xiaoyi", "yuanbao", "wechat", "slack", "onebot",
}


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        "wechat_customer_registration_test_plugin",
        PLUGIN_ROOT / "plugin.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Plugin entry")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _PluginApi:
    def __init__(self):
        self.channels = []

    def register_channel(self, **kwargs):
        self.channels.append(kwargs)


class WeChatCustomerChannelRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_channel = install_qwenpaw_v2_1_stubs()
        cls.module = _load_plugin()

    def test_plugin_registers_unique_native_channel_and_safe_config_fields(self):
        api = _PluginApi()
        self.module.plugin.register(api)
        self.assertEqual(len(api.channels), 1)
        registration = api.channels[0]
        channel_class = registration["channel_class"]
        self.assertTrue(issubclass(channel_class, self.base_channel))
        self.assertEqual(channel_class.channel, "wechat_customer")
        self.assertNotIn(channel_class.channel, BUILTIN_V2_1_CHANNEL_KEYS)

        fields = registration["config_fields"]
        self.assertEqual(
            [item["name"] for item in fields],
            [
                "corp_id",
                "app_secret",
                "callback_token",
                "encoding_aes_key",
                "open_kfid",
                "gateway_url",
            ],
        )
        types = {item["name"]: item["type"] for item in fields}
        self.assertEqual(types["app_secret"], "password")
        self.assertEqual(types["callback_token"], "password")
        self.assertEqual(types["encoding_aes_key"], "password")
        self.assertEqual(types["corp_id"], "text")
        self.assertEqual(types["open_kfid"], "text")
        self.assertTrue(all("value" not in item for item in fields))

    def test_release_zip_imports_without_repository_or_shared_namespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = build_qwenpaw_plugins(
                REPOSITORY_ROOT,
                root / "dist",
                names=["wechat-customer-channel-plugin"],
            )[0]
            extraction = root / "installed"
            with zipfile.ZipFile(result.archive) as package:
                package.extractall(extraction)
                names = set(package.namelist())
            namespace = "qwenpaw_plugin_wechat_customer_extension_channel"
            for required in (
                "plugin.json",
                "plugin.py",
                f"{namespace}/channel.py",
                f"{namespace}/gateway_bridge.py",
                f"{namespace}/gateway_facade.py",
                f"{namespace}/adapter/wechat_customer/runtime.py",
            ):
                self.assertIn(required, names)

            script = r'''
import dataclasses, enum, importlib.util, json, pathlib, sys, types
q=types.ModuleType("qwenpaw"); app=types.ModuleType("qwenpaw.app")
channels=types.ModuleType("qwenpaw.app.channels"); base=types.ModuleType("qwenpaw.app.channels.base")
renderer=types.ModuleType("qwenpaw.app.channels.renderer"); schemas=types.ModuleType("qwenpaw.schemas")
class D:
 @classmethod
 def from_config(cls, config): return cls()
class C(str, enum.Enum): TEXT="text"
@dataclasses.dataclass
class T: type:C; text:str
class B:
 def __init__(self, process, **kwargs): self._process=process; self._enqueue=None
 def build_agent_request_from_user_content(self, **kwargs): return types.SimpleNamespace(**kwargs)
base.BaseChannel=B; base.OnReplySent=object; base.ProcessHandler=object
renderer.ChannelDisplayConfig=D; schemas.ContentType=C; schemas.TextContent=T
q.app=app; q.schemas=schemas; app.channels=channels; channels.base=base; channels.renderer=renderer
sys.modules.update({"qwenpaw":q,"qwenpaw.app":app,"qwenpaw.app.channels":channels,"qwenpaw.app.channels.base":base,"qwenpaw.app.channels.renderer":renderer,"qwenpaw.schemas":schemas})
root=pathlib.Path.cwd(); spec=importlib.util.spec_from_file_location("installed_wechat_customer", root/"plugin.py")
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class Api:
 def register_channel(self, **kwargs): self.value=kwargs
api=Api(); module.plugin.register(api)
repo=pathlib.Path(sys.argv[1]).resolve()
print(json.dumps({"channel":api.value["channel_class"].channel,"self_contained":module.SELF_CONTAINED,"repo_on_path":any(pathlib.Path(p or ".").resolve()==repo for p in sys.path)}))
'''
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            completed = subprocess.run(
                [
                    str(Path(getattr(sys, "_base_executable", sys.executable))),
                    "-I",
                    "-c",
                    script,
                    str(REPOSITORY_ROOT),
                ],
                cwd=extraction,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["channel"], "wechat_customer")
            self.assertTrue(payload["self_contained"])
            self.assertFalse(payload["repo_on_path"])


if __name__ == "__main__":
    unittest.main()
