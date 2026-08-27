"""Structured result contracts shared by independently packaged Skills."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class SkillStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    MODEL_RUNTIME_REQUIRED = "MODEL_RUNTIME_REQUIRED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_INPUT = "INVALID_INPUT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SkillResult:
    status: SkillStatus
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    error: Mapping[str, Any] | None = None
    capabilities: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["artifacts"] = list(self.artifacts)
        return value


def result(
    status: SkillStatus,
    message: str,
    *,
    data: Mapping[str, Any] | None = None,
    artifacts: Sequence[Mapping[str, Any]] = (),
    error_code: str | None = None,
    error_detail: str | None = None,
    capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    error = None
    if error_code:
        error = {"code": error_code, "detail": error_detail or message}
    return SkillResult(
        status=status,
        message=message,
        data=data or {},
        artifacts=artifacts,
        error=error,
        capabilities=capabilities or {},
    ).to_dict()


def invalid(message: str, *, code: str = "INVALID_INPUT") -> dict[str, Any]:
    return result(SkillStatus.INVALID_INPUT, message, error_code=code)


def failed(exc: Exception) -> dict[str, Any]:
    return result(
        SkillStatus.FAILED,
        "Skill execution failed",
        error_code=type(exc).__name__,
        error_detail=str(exc),
    )
