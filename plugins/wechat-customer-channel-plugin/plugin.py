"""QwenPaw Plugin entry for the existing WeChat Customer Extension Adapter."""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Callable

PLUGIN_ROOT = Path(__file__).resolve().parent
SOURCE_REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
PACKAGED_ADAPTER_PATH = PLUGIN_ROOT / "adapter" / "wechat_customer" / "runtime.py"
PACKAGED_WRAPPER_PATH = PLUGIN_ROOT / "runtime" / "wrapper.py"
SELF_CONTAINED = PACKAGED_ADAPTER_PATH.is_file() and PACKAGED_WRAPPER_PATH.is_file()

CONFIG_FIELDS = [
    {
        "name": "corp_id",
        "label": {"zh": "企业 ID", "en": "Corp ID"},
        "type": "text",
        "required": True,
        "help": {"zh": "历史 Gateway 的 CORP_ID", "en": "Gateway CORP_ID"},
    },
    {
        "name": "app_secret",
        "label": {"zh": "应用 Secret", "en": "App Secret"},
        "type": "password",
        "required": True,
    },
    {
        "name": "callback_token",
        "label": {"zh": "回调 Token", "en": "Callback Token"},
        "type": "password",
        "required": True,
    },
    {
        "name": "encoding_aes_key",
        "label": {"zh": "EncodingAESKey", "en": "EncodingAESKey"},
        "type": "password",
        "required": True,
    },
    {
        "name": "open_kfid",
        "label": {"zh": "微信客服 ID", "en": "Open KF ID"},
        "type": "text",
        "required": True,
    },
    {
        "name": "gateway_url",
        "label": {"zh": "Gateway 地址", "en": "Gateway URL"},
        "type": "text",
        "required": True,
        "default": "http://127.0.0.1:8798",
        "help": {
            "zh": "独立 Gateway Facade 地址",
            "en": "External Gateway facade URL",
        },
    },
]


def _load_source_wrapper_class():
    wrapper_path = (
        SOURCE_REPOSITORY_ROOT / "plugins" / "runtime-wrapper" / "runtime.py"
    )
    spec = importlib.util.spec_from_file_location(
        "qwenpaw_platform_official_plugin_runtime",
        wrapper_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Runtime wrapper: {wrapper_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.OfficialPluginRuntimeWrapper


if SELF_CONTAINED:
    REPOSITORY_ROOT = PLUGIN_ROOT
    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))
    from adapter.wechat_customer.runtime import WeChatCustomerRuntimeAdapter
    from runtime.wrapper import OfficialPluginRuntimeWrapper
else:
    REPOSITORY_ROOT = SOURCE_REPOSITORY_ROOT
    if str(REPOSITORY_ROOT) not in sys.path:
        sys.path.insert(0, str(REPOSITORY_ROOT))
    WeChatCustomerRuntimeAdapter = importlib.import_module(
        "adapters.wechat_customer.runtime"
    ).WeChatCustomerRuntimeAdapter
    OfficialPluginRuntimeWrapper = _load_source_wrapper_class()

from core.contracts import DeliveryReceipt, MessageEvent
from core.extensions.lifecycle import ExtensionLifecycleManager
from core.extensions.runtime import ExtensionRuntimeGateway, PluginRuntimeBridge
from core.streaming import StreamingBridge


class WeChatCustomerChannelPlugin:
    """Thin entry preserving Gateway ownership of state and provider I/O."""

    extension_id = "wechat-customer"

    def __init__(self) -> None:
        self.runtime = OfficialPluginRuntimeWrapper(
            REPOSITORY_ROOT,
            self.extension_id,
        )

    @property
    def adapter(self) -> WeChatCustomerRuntimeAdapter:
        adapter = self.runtime.adapter
        if not isinstance(adapter, WeChatCustomerRuntimeAdapter):
            raise TypeError("bound Adapter is not WeChatCustomerRuntimeAdapter")
        return adapter

    def load_extension_manifest(self):
        """Load metadata without importing or starting the historical Gateway."""

        return self.runtime.load_extension_manifest()

    def configure_runtime(
        self,
        *,
        lifecycle_manager: ExtensionLifecycleManager,
        transport: Any,
        skill_invoker: Any = None,
    ) -> ExtensionRuntimeGateway:
        """Bind injected dependencies to the existing Adapter and Gateway."""

        metadata = self.load_extension_manifest()
        plugin_bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT,
            self.runtime.registry,
            lifecycle_manager,
            probe=transport,
        )
        adapter = WeChatCustomerRuntimeAdapter(
            plugin_bridge,
            transport,
            instance_id="wechat-customer-qwenpaw-plugin",
        )
        gateway = ExtensionRuntimeGateway(
            self.runtime.registry,
            lifecycle_manager,
            skill_invoker=skill_invoker,
            streaming_bridge=StreamingBridge(),
            message_receivers={metadata.name: adapter},
        )
        self.runtime.bind(
            lifecycle_manager=lifecycle_manager,
            gateway=gateway,
            adapter=adapter,
        )
        return gateway

    def receive_message(self) -> MessageEvent | None:
        return self.runtime.receive_message()

    def forward_message_event(
        self, handler: Callable[[MessageEvent], Any]
    ) -> Any | None:
        return self.runtime.forward_message_event(handler)

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        return self.runtime.send_response(message, response)

    def sync_lifecycle(self, action: str, **kwargs: Any) -> Any:
        return self.runtime.sync_lifecycle(action, **kwargs)

    def load_channel_class(self):
        """Load the native Channel from a process-private Plugin namespace."""

        if SELF_CONTAINED:
            namespace = globals().get("PACKAGED_NAMESPACE")
            if not isinstance(namespace, str) or not namespace:
                raise RuntimeError("packaged Plugin namespace is not initialized")
            return importlib.import_module(
                f"{namespace}.channel"
            ).WeChatCustomerChannel

        package_name = "qwenpaw_wechat_customer_channel_source"
        package = sys.modules.get(package_name)
        if package is None:
            package_init = PLUGIN_ROOT / "__init__.py"
            spec = importlib.util.spec_from_file_location(
                package_name,
                package_init,
                submodule_search_locations=[str(PLUGIN_ROOT)],
            )
            if spec is None or spec.loader is None:
                raise RuntimeError(f"cannot load Channel package: {package_init}")
            package = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = package
            spec.loader.exec_module(package)
        return importlib.import_module(
            f"{package_name}.channel"
        ).WeChatCustomerChannel

    def register(self, api: Any) -> None:
        """Register the native Channel through QwenPaw v2.1.0 PluginApi."""

        register_channel = getattr(api, "register_channel", None)
        if not callable(register_channel):
            raise TypeError("QwenPaw PluginApi must provide register_channel")
        register_channel(
            channel_class=self.load_channel_class(),
            label="微信客服",
            description="企业微信 open_kfid 客服 Gateway Channel",
            config_fields=CONFIG_FIELDS,
        )


plugin = WeChatCustomerChannelPlugin()
