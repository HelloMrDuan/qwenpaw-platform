"""Lazy dispatcher for the Core Productivity Skill Pack."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping

from .models import failed, invalid


HANDLERS = {
    "image-toolkit": "image_tools",
    "photo-restoration": "image_tools",
    "image-background-tools": "image_tools",
    "image-quality-enhancer": "image_tools",
    "advanced-ocr": "ocr_media",
    "media-transcriber": "ocr_media",
    "sql-diagnostics": "diagnostics",
    "log-incident-analyzer": "diagnostics",
    "api-debugger": "diagnostics",
    "ops-troubleshooter": "diagnostics",
    "network-diagnostics": "diagnostics",
    "config-diagnostics": "diagnostics",
    "archive-inspector": "data_files",
    "data-profiler": "data_files",
    "document-batch-processor": "data_files",
    "release-notes": "research_release",
    "web-research-report": "research_release",
}


def execute_skill(skill_name: str, request: Mapping[str, Any]) -> dict[str, Any]:
    if skill_name not in HANDLERS:
        return invalid(f"Unknown productivity Skill: {skill_name}", code="UNKNOWN_SKILL")
    if not isinstance(request, Mapping):
        return invalid("Request must be a JSON object")
    try:
        module = import_module(f"{__package__}.handlers.{HANDLERS[skill_name]}")
        return module.execute(skill_name, dict(request))
    except Exception as exc:  # The CLI must never claim success after an exception.
        return failed(exc)
