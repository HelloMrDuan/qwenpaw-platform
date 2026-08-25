"""Official QwenPaw Plugin entry for the existing Telegram Extension Adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any, Callable

from adapters.telegram.runtime import TelegramRuntimeAdapter
from core.contracts import DeliveryReceipt, MessageEvent
from core.extensions.lifecycle import ExtensionLifecycleManager
from core.extensions.runtime import (
    ExtensionRuntimeGateway,
    PluginRuntimeBridge,
)
from core.streaming import StreamingBridge


PLUGIN_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
WRAPPER_MODULE_PATH = REPOSITORY_ROOT / "plugins" / "runtime-wrapper" / "runtime.py"


def _load_wrapper_class():
    spec = importlib.util.spec_from_file_location(
        "qwenpaw_platform_official_plugin_runtime",
        WRAPPER_MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Runtime wrapper: {WRAPPER_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.OfficialPluginRuntimeWrapper


OfficialPluginRuntimeWrapper = _load_wrapper_class()


class TelegramChannelPlugin:
    """Thin official entry; all Telegram conversion stays in the existing Adapter."""

    extension_id = "telegram"

    def __init__(self) -> None:
        self.runtime = OfficialPluginRuntimeWrapper(
            REPOSITORY_ROOT,
            self.extension_id,
        )

    @property
    def adapter(self) -> TelegramRuntimeAdapter:
        adapter = self.runtime.adapter
        if not isinstance(adapter, TelegramRuntimeAdapter):
            raise TypeError("bound Adapter is not TelegramRuntimeAdapter")
        return adapter

    def load_extension_manifest(self):
        """Load validated Telegram metadata without importing the recovered Bridge."""

        return self.runtime.load_extension_manifest()

    def configure_runtime(
        self,
        *,
        lifecycle_manager: ExtensionLifecycleManager,
        transport: Any,
        skill_invoker: Any = None,
    ) -> ExtensionRuntimeGateway:
        """Bind injected offline/supervised dependencies to the existing Gateway."""

        metadata = self.load_extension_manifest()
        plugin_bridge = PluginRuntimeBridge(
            REPOSITORY_ROOT,
            self.runtime.registry,
            lifecycle_manager,
            probe=transport,
        )
        adapter = TelegramRuntimeAdapter(
            plugin_bridge,
            transport,
            instance_id="telegram-qwenpaw-plugin",
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

    def register(self, api: Any) -> None:
        """Official PluginApi entry; metadata loading remains process-safe."""

        register_hook = getattr(api, "register_startup_hook", None)
        if not callable(register_hook):
            raise TypeError("QwenPaw PluginApi must provide register_startup_hook")
        register_hook(
            "telegram-extension-manifest",
            self.load_extension_manifest,
            priority=100,
        )


plugin = TelegramChannelPlugin()
