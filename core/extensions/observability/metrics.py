"""Thread-safe in-memory counters for Extension calls and outcomes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock

from .models import ExtensionCallMetrics, require_text, utc_timestamp


Clock = Callable[[], datetime]


class ExtensionMetricsStore:
    """Record one terminal success/failure outcome per Extension invocation."""

    def __init__(self, *, clock: Clock | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._counts: dict[str, tuple[int, int]] = {}
        self._updated_at: dict[str, str] = {}
        self._lock = RLock()

    def record_call(self, extension_name: str, *, success: bool) -> ExtensionCallMetrics:
        name = require_text(extension_name, "extension_name")
        if not isinstance(success, bool):
            raise TypeError("success must be a boolean")
        with self._lock:
            successes, failures = self._counts.get(name, (0, 0))
            if success:
                successes += 1
            else:
                failures += 1
            observed_at = utc_timestamp(self._clock())
            self._counts[name] = (successes, failures)
            self._updated_at[name] = observed_at
            return self._snapshot_unlocked(name)

    def get(self, extension_name: str) -> ExtensionCallMetrics:
        name = require_text(extension_name, "extension_name")
        with self._lock:
            if name not in self._counts:
                raise KeyError(f"Extension metrics not found: {name}")
            return self._snapshot_unlocked(name)

    def list(self) -> tuple[ExtensionCallMetrics, ...]:
        with self._lock:
            return tuple(
                self._snapshot_unlocked(name) for name in sorted(self._counts)
            )

    def _snapshot_unlocked(self, name: str) -> ExtensionCallMetrics:
        successes, failures = self._counts[name]
        return ExtensionCallMetrics(
            extension_name=name,
            calls=successes + failures,
            successes=successes,
            failures=failures,
            updated_at=self._updated_at[name],
        )
