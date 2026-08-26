"""Out-of-process facade for the historical WeChat Customer Gateway.

The facade never owns provider credentials, cursor state, deduplication, or the
Gateway database. It only speaks companion bridge endpoints exposed beside the
independently supervised historical Gateway.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
from threading import RLock
from typing import Any, Protocol, runtime_checkable
import urllib.error
import urllib.request

try:
    from .core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState
except ImportError:  # Source-repository execution.
    from core.extensions.runtime import ExternalServiceSnapshot, ExternalServiceState


class GatewayFacadeError(RuntimeError):
    """Raised when the external Gateway facade cannot complete an operation."""


@runtime_checkable
class GatewayFacade(Protocol):
    """Minimal process boundary consumed by the native Channel wrapper."""

    external_api_verified: bool

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def check(self, descriptor: object) -> ExternalServiceSnapshot: ...

    def receive_event(self) -> Mapping[str, Any] | None: ...

    def send_text(
        self,
        external_userid: str,
        open_kfid: str,
        text: str,
        reply_to: str,
    ) -> str | None: ...


class HttpGatewayFacade:
    """HTTP client for a separately running Gateway compatibility facade.

    ``/healthz`` exists in the recovered Gateway. ``/bridge/events`` and
    ``/bridge/send`` belong to the compatibility facade and must preserve the
    Gateway's cursor/DB/dedup ownership.
    """

    external_api_verified = False

    def __init__(self, gateway_url: str, *, timeout: float = 2.0) -> None:
        normalized = str(gateway_url or "").strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("gateway_url must be an http(s) URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.gateway_url = normalized
        self.timeout = float(timeout)
        self._started = False
        self._lock = RLock()

    def start(self) -> None:
        with self._lock:
            self._started = True

    def stop(self) -> None:
        with self._lock:
            self._started = False

    def check(self, descriptor: object) -> ExternalServiceSnapshot:
        del descriptor
        try:
            request = urllib.request.Request(f"{self.gateway_url}/healthz", method="GET")
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reachable = 200 <= int(response.status) < 300
            return ExternalServiceSnapshot(
                state=(
                    ExternalServiceState.RUNNING
                    if reachable
                    else ExternalServiceState.FAILED
                ),
                reachable=reachable,
                detail=(
                    "WeChat Customer Gateway health endpoint is reachable"
                    if reachable
                    else "WeChat Customer Gateway health endpoint is unhealthy"
                ),
            )
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            return ExternalServiceSnapshot(
                state=ExternalServiceState.STOPPED,
                reachable=False,
                detail=f"WeChat Customer Gateway is not reachable: {type(exc).__name__}",
            )

    def receive_event(self) -> Mapping[str, Any] | None:
        with self._lock:
            if not self._started:
                return None
        request = urllib.request.Request(
            f"{self.gateway_url}/bridge/events",
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if int(response.status) == 204:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                return None
            raise GatewayFacadeError(
                f"Gateway event bridge returned HTTP {exc.code}"
            ) from exc
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise GatewayFacadeError(
                f"Gateway event bridge failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise GatewayFacadeError("Gateway event bridge returned a non-object")
        return payload

    def send_text(
        self,
        external_userid: str,
        open_kfid: str,
        text: str,
        reply_to: str,
    ) -> str | None:
        body = json.dumps(
            {
                "external_userid": external_userid,
                "open_kfid": open_kfid,
                "text": text,
                "reply_to": reply_to,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.gateway_url}/bridge/send",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise GatewayFacadeError(
                f"Gateway send bridge failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(payload, Mapping) or payload.get("accepted") is not True:
            raise GatewayFacadeError("Gateway did not accept the outbound message")
        provider_message_id = payload.get("provider_message_id")
        return str(provider_message_id) if provider_message_id is not None else None
