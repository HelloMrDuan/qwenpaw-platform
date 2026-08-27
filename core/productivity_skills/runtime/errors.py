"""Structured failures raised by optional model Runtime adapters."""

from __future__ import annotations


class RuntimeAdapterError(RuntimeError):
    """Base error for an adapter that exists but cannot complete execution."""


class RuntimeUnavailableError(RuntimeAdapterError):
    """The package, configured model, or model cache is unavailable."""


class RuntimeExecutionError(RuntimeAdapterError):
    """The Runtime was selected but loading or inference failed."""
