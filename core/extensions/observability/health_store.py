"""Thread-safe local history for Extension lifecycle and health observations."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from threading import RLock

from core.extensions.lifecycle import HealthReport, LifecycleRecord

from .models import (
    ExtensionHealthObservation,
    ExtensionStateObservation,
    require_text,
)


Clock = Callable[[], datetime]


class ExtensionHealthStore:
    """Keep bounded process-local health and lifecycle histories per Extension."""

    def __init__(
        self,
        *,
        max_history_per_extension: int = 100,
        clock: Clock | None = None,
    ) -> None:
        if type(max_history_per_extension) is not int or max_history_per_extension < 1:
            raise ValueError("max_history_per_extension must be a positive integer")
        self._max_history = max_history_per_extension
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._health: dict[str, deque[ExtensionHealthObservation]] = defaultdict(
            self._new_health_history
        )
        self._states: dict[str, deque[ExtensionStateObservation]] = defaultdict(
            self._new_state_history
        )
        self._lock = RLock()

    def record_health(
        self,
        report: HealthReport,
        *,
        trace_id: str | None = None,
    ) -> ExtensionHealthObservation:
        observation = ExtensionHealthObservation.from_report(
            report,
            observed_at=self._clock(),
            trace_id=trace_id,
        )
        with self._lock:
            self._health[observation.extension_name].append(observation)
        return observation

    def record_state(self, record: LifecycleRecord) -> ExtensionStateObservation:
        observation = ExtensionStateObservation.from_lifecycle(
            record, observed_at=self._clock()
        )
        with self._lock:
            self._states[observation.extension_name].append(observation)
        return observation

    def health_history(
        self, extension_name: str
    ) -> tuple[ExtensionHealthObservation, ...]:
        name = require_text(extension_name, "extension_name")
        with self._lock:
            return tuple(self._health.get(name, ()))

    def state_history(
        self, extension_name: str
    ) -> tuple[ExtensionStateObservation, ...]:
        name = require_text(extension_name, "extension_name")
        with self._lock:
            return tuple(self._states.get(name, ()))

    def latest_health(self, extension_name: str) -> ExtensionHealthObservation | None:
        history = self.health_history(extension_name)
        return history[-1] if history else None

    def latest_state(self, extension_name: str) -> ExtensionStateObservation | None:
        history = self.state_history(extension_name)
        return history[-1] if history else None

    def extension_names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(set(self._health).union(self._states)))

    def _new_health_history(self) -> deque[ExtensionHealthObservation]:
        return deque(maxlen=self._max_history)

    def _new_state_history(self) -> deque[ExtensionStateObservation]:
        return deque(maxlen=self._max_history)
