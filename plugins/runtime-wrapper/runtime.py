"""Generic bridge from repository Extensions to an official QwenPaw Plugin entry.

This module does not import QwenPaw, start an Extension process, or implement a
provider transport.  An official Plugin entry injects the existing Adapter and
Runtime Gateway after the host has supplied the required local dependencies.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.contracts import DeliveryReceipt, MessageEvent
from core.extensions import ExtensionMetadata, ExtensionRegistry
from core.extensions.runtime import ExtensionRuntimeGateway


class OfficialPluginRuntimeError(RuntimeError):
    """Raised when an official Plugin wrapper is not safely configured."""


class OfficialPluginRuntimeWrapper:
    """Bind one discovered Extension to the existing Runtime Gateway."""

    _LIFECYCLE_ACTIONS = frozenset(
        {"verify", "enable", "disable", "start", "stop", "health", "rollback"}
    )

    def __init__(self, repository_root: str | Path, extension_id: str) -> None:
        self.repository_root = Path(repository_root).resolve()
        if not isinstance(extension_id, str) or not extension_id.strip():
            raise ValueError("extension_id must be non-empty text")
        self.extension_id = extension_id.strip()
        self.registry = ExtensionRegistry(self.repository_root)
        self._metadata: ExtensionMetadata | None = None
        self._lifecycle_manager: Any | None = None
        self._gateway: ExtensionRuntimeGateway | None = None
        self._adapter: Any | None = None

    @property
    def metadata(self) -> ExtensionMetadata:
        if self._metadata is None:
            raise OfficialPluginRuntimeError("Extension Manifest has not been loaded")
        return self._metadata

    @property
    def adapter(self) -> Any:
        if self._adapter is None:
            raise OfficialPluginRuntimeError("Extension Adapter has not been bound")
        return self._adapter

    def load_extension_manifest(self) -> ExtensionMetadata:
        """Discover and validate the internal Manifest without loading its entrypoint."""

        if self._metadata is not None:
            return self._metadata
        self.registry.discover()
        metadata = self.registry.get(self.extension_id)
        if metadata is None:
            raise OfficialPluginRuntimeError(
                f"Extension is not registered: {self.extension_id}"
            )
        self._metadata = metadata
        return metadata

    def bind(
        self,
        *,
        lifecycle_manager: Any,
        gateway: ExtensionRuntimeGateway,
        adapter: Any,
    ) -> None:
        """Attach pre-built Extension components without starting provider code."""

        metadata = self.load_extension_manifest()
        if not isinstance(gateway, ExtensionRuntimeGateway):
            raise TypeError("gateway must be an ExtensionRuntimeGateway")
        if not callable(getattr(adapter, "receive_message", None)):
            raise TypeError("adapter must implement receive_message()")
        if not callable(getattr(adapter, "send_response", None)):
            raise TypeError("adapter must implement send_response(message, response)")
        registered = gateway.registry.get(metadata.name)
        if registered != metadata:
            raise OfficialPluginRuntimeError(
                "Gateway Registry does not contain the same Extension metadata"
            )
        self._lifecycle_manager = lifecycle_manager
        self._gateway = gateway
        self._adapter = adapter

    def receive_message(self) -> MessageEvent | None:
        """Receive one normalized event through the existing Runtime Gateway."""

        if self._gateway is None:
            raise OfficialPluginRuntimeError("Extension Runtime has not been bound")
        result = self._gateway.receive_message(self.extension_id)
        if result is None:
            return None
        if not isinstance(result.value, MessageEvent):
            raise OfficialPluginRuntimeError("Gateway did not return a MessageEvent")
        return result.value

    def forward_message_event(
        self, handler: Callable[[MessageEvent], Any]
    ) -> Any | None:
        """Forward one normalized event to an injected QwenPaw-side handler."""

        if not callable(handler):
            raise TypeError("handler must be callable")
        message = self.receive_message()
        return None if message is None else handler(message)

    def send_response(self, message: MessageEvent, response: str) -> DeliveryReceipt:
        """Delegate outbound conversion to the existing Adapter implementation."""

        receipt = self.adapter.send_response(message, response)
        if not isinstance(receipt, DeliveryReceipt):
            raise OfficialPluginRuntimeError(
                "Extension Adapter did not return a DeliveryReceipt"
            )
        return receipt

    def sync_lifecycle(self, action: str, **kwargs: Any) -> Any:
        """Mirror an approved local lifecycle action without controlling a process."""

        if self._lifecycle_manager is None:
            raise OfficialPluginRuntimeError("Extension Runtime has not been bound")
        if action not in self._LIFECYCLE_ACTIONS:
            raise OfficialPluginRuntimeError(
                f"unsupported lifecycle action: {action}"
            )
        operation = getattr(self._lifecycle_manager, action, None)
        if not callable(operation):
            raise OfficialPluginRuntimeError(
                f"lifecycle manager does not implement: {action}"
            )
        return operation(self.extension_id, **kwargs)
