"""Offline Extension lifecycle simulation APIs."""

from .health import LocalHealthChecker
from .manager import (
    ExtensionLifecycleError,
    ExtensionLifecycleManager,
    InvalidLifecycleTransition,
    LifecycleVerificationError,
)
from .models import (
    LIFECYCLE_SCHEMA_VERSION,
    ExtensionState,
    HealthReport,
    LifecycleAction,
    LifecycleRecord,
)

__all__ = [
    "ExtensionLifecycleError",
    "ExtensionLifecycleManager",
    "ExtensionState",
    "HealthReport",
    "InvalidLifecycleTransition",
    "LIFECYCLE_SCHEMA_VERSION",
    "LifecycleAction",
    "LifecycleRecord",
    "LifecycleVerificationError",
    "LocalHealthChecker",
]
