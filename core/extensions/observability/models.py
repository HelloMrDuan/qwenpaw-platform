"""Immutable records emitted by the local Extension observability layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from core.extensions.lifecycle import ExtensionState, HealthReport, LifecycleRecord


OBSERVABILITY_SCHEMA_VERSION = "qwenpaw-extension-observability.v1"


def require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value.strip()


def utc_timestamp(value: datetime | str) -> str:
    """Normalize a timezone-aware datetime or validate an RFC 3339 UTC string."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("observability timestamp must be timezone-aware")
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    text = require_text(value, "observed_at")
    if not text.endswith("Z"):
        raise ValueError("observed_at must be an RFC 3339 UTC value ending in Z")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("observed_at must be a valid RFC 3339 UTC value") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("observed_at must use UTC")
    return text


@dataclass(frozen=True, slots=True)
class ExtensionStateObservation:
    extension_name: str
    version: str
    state: ExtensionState
    revision: int
    action: str
    observed_at: str
    error: str | None = None
    schema_version: str = OBSERVABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVABILITY_SCHEMA_VERSION:
            raise ValueError("unsupported observability schema version")
        object.__setattr__(
            self, "extension_name", require_text(self.extension_name, "extension_name")
        )
        object.__setattr__(self, "version", require_text(self.version, "version"))
        if isinstance(self.state, str):
            object.__setattr__(self, "state", ExtensionState(self.state))
        if not isinstance(self.state, ExtensionState):
            raise TypeError("state must be an ExtensionState")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        object.__setattr__(self, "action", require_text(self.action, "action"))
        object.__setattr__(self, "observed_at", utc_timestamp(self.observed_at))
        if self.error is not None:
            object.__setattr__(self, "error", require_text(self.error, "error"))

    @classmethod
    def from_lifecycle(
        cls, record: LifecycleRecord, *, observed_at: datetime | str
    ) -> "ExtensionStateObservation":
        if not isinstance(record, LifecycleRecord):
            raise TypeError("record must be a LifecycleRecord")
        return cls(
            extension_name=record.name,
            version=record.version,
            state=record.state,
            revision=record.revision,
            action=record.last_action.value,
            observed_at=utc_timestamp(observed_at),
            error=record.error,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extension_name": self.extension_name,
            "version": self.version,
            "state": self.state.value,
            "revision": self.revision,
            "action": self.action,
            "observed_at": self.observed_at,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class ExtensionHealthObservation:
    extension_name: str
    version: str
    state: ExtensionState
    healthy: bool
    deployment_verified: bool
    runtime_probe_performed: bool
    code: str
    message: str
    observed_at: str
    trace_id: str | None = None
    schema_version: str = OBSERVABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVABILITY_SCHEMA_VERSION:
            raise ValueError("unsupported observability schema version")
        object.__setattr__(
            self, "extension_name", require_text(self.extension_name, "extension_name")
        )
        object.__setattr__(self, "version", require_text(self.version, "version"))
        if isinstance(self.state, str):
            object.__setattr__(self, "state", ExtensionState(self.state))
        if not isinstance(self.state, ExtensionState):
            raise TypeError("state must be an ExtensionState")
        for field_name in (
            "healthy",
            "deployment_verified",
            "runtime_probe_performed",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a boolean")
        object.__setattr__(self, "code", require_text(self.code, "code"))
        object.__setattr__(self, "message", require_text(self.message, "message"))
        object.__setattr__(self, "observed_at", utc_timestamp(self.observed_at))
        if self.trace_id is not None:
            object.__setattr__(
                self, "trace_id", require_text(self.trace_id, "trace_id")
            )

    @classmethod
    def from_report(
        cls,
        report: HealthReport,
        *,
        observed_at: datetime | str,
        trace_id: str | None = None,
    ) -> "ExtensionHealthObservation":
        if not isinstance(report, HealthReport):
            raise TypeError("report must be a HealthReport")
        return cls(
            extension_name=report.name,
            version=report.version,
            state=report.state,
            healthy=report.healthy,
            deployment_verified=report.deployment_verified,
            runtime_probe_performed=report.runtime_probe_performed,
            code=report.code,
            message=report.message,
            observed_at=utc_timestamp(observed_at),
            trace_id=trace_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extension_name": self.extension_name,
            "version": self.version,
            "state": self.state.value,
            "healthy": self.healthy,
            "deployment_verified": self.deployment_verified,
            "runtime_probe_performed": self.runtime_probe_performed,
            "code": self.code,
            "message": self.message,
            "observed_at": self.observed_at,
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True, slots=True)
class ExtensionCallMetrics:
    extension_name: str
    calls: int
    successes: int
    failures: int
    updated_at: str
    schema_version: str = OBSERVABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVABILITY_SCHEMA_VERSION:
            raise ValueError("unsupported observability schema version")
        object.__setattr__(
            self, "extension_name", require_text(self.extension_name, "extension_name")
        )
        for field_name in ("calls", "successes", "failures"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.successes + self.failures != self.calls:
            raise ValueError("successes plus failures must equal calls")
        object.__setattr__(self, "updated_at", utc_timestamp(self.updated_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extension_name": self.extension_name,
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class ExtensionTraceEvent:
    extension_name: str
    trace_id: str
    event_id: str
    event_type: str
    observed_at: str
    session_id: str | None = None
    sequence: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = OBSERVABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVABILITY_SCHEMA_VERSION:
            raise ValueError("unsupported observability schema version")
        for field_name in ("extension_name", "trace_id", "event_id", "event_type"):
            object.__setattr__(
                self,
                field_name,
                require_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "observed_at", utc_timestamp(self.observed_at))
        if self.session_id is not None:
            object.__setattr__(
                self, "session_id", require_text(self.session_id, "session_id")
            )
        if self.sequence is not None and (
            type(self.sequence) is not int or self.sequence < 1
        ):
            raise ValueError("sequence must be null or a positive integer")
        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "extension_name": self.extension_name,
            "trace_id": self.trace_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "observed_at": self.observed_at,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "metadata": dict(self.metadata),
        }
