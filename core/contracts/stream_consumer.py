"""Consumer contract for Extension-layer streaming events."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .streaming import StreamEvent


@runtime_checkable
class StreamConsumer(Protocol):
    """Synchronous event consumer used by the local Streaming Bridge.

    Transport-specific buffering, retries and network I/O belong to future
    Runtime or Channel adapters, not to this Extension contract.
    """

    def on_event(self, event: StreamEvent) -> None:
        """Consume one already validated StreamEvent."""
        ...
