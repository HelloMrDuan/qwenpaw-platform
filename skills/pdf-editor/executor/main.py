"""SkillRequest -> deterministic PDF Editor -> SkillResult adapter.

This module owns contract translation only. All PDF mutation remains in
``scripts/pdf_editor.py`` so the QwenPaw SKILL.md / CLI path stays compatible.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.contracts import (  # noqa: E402
    Artifact,
    ArtifactKind,
    SkillRequest,
    SkillResult,
    STREAM_SCHEMA_VERSION,
    StreamEvent,
    StreamEventType,
    StreamSource,
)


ENGINE = SKILL_ROOT / "scripts" / "pdf_editor.py"
ArtifactResolver = Callable[[Artifact], str | Path]
ArtifactPublisher = Callable[[Path], Artifact]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _EventBuilder:
    def __init__(self, request: SkillRequest):
        context = request.context
        self.request = request
        self.sequence = 0
        self.stream_id = str(context.get("stream_id") or f"str_{request.request_id}")
        self.trace_id = str(context.get("trace_id") or f"trc_{request.request_id}")
        self.session_id = str(context.get("session_id") or f"ses_{request.request_id}")
        self.conversation_id = str(
            context.get("conversation_id") or f"conv_{request.request_id}"
        )
        self.task_id = str(context.get("task_id") or f"task_{request.request_id}")
        self.tool_call_id = str(context.get("tool_call_id") or f"call_{request.request_id}")

    def create(self, event: StreamEventType, payload: Mapping[str, Any]) -> StreamEvent:
        self.sequence += 1
        return StreamEvent(
            version=STREAM_SCHEMA_VERSION,
            event_id=f"evt_{self.request.request_id}_{self.sequence:04d}",
            event=event,
            stream_id=self.stream_id,
            sequence=self.sequence,
            timestamp=_utc_now(),
            trace_id=self.trace_id,
            session_id=self.session_id,
            conversation_id=self.conversation_id,
            task_id=self.task_id,
            source=StreamSource(type="skill", name="pdf-editor"),
            payload=payload,
        )

    def tool_payload(self, operation: str, **extra: Any) -> dict[str, Any]:
        return {
            "tool_call_id": self.tool_call_id,
            "parent_tool_call_id": self.request.context.get("parent_tool_call_id"),
            "tool_type": "skill",
            "tool": "pdf-editor",
            "operation": operation,
            "attempt": int(self.request.context.get("attempt", 1)),
            **extra,
        }


def _resolve_files(
    request: SkillRequest, resolver: ArtifactResolver
) -> tuple[dict[str, Path], Artifact]:
    if not request.files:
        raise ValueError("PDF Editor requires at least one input Artifact")
    resolved: dict[str, Path] = {}
    for artifact in request.files:
        path = Path(resolver(artifact)).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Resolved Artifact does not exist: {artifact.id}")
        resolved[artifact.id] = path
        resolved[artifact.uri] = path
    input_id = str(request.parameters.get("input_artifact_id") or request.files[0].id)
    if input_id not in resolved:
        raise ValueError(f"input_artifact_id is not present in files: {input_id}")
    input_artifact = next(
        item for item in request.files if item.id == input_id or item.uri == input_id
    )
    if resolved[input_id].suffix.lower() != ".pdf":
        raise ValueError("The primary input Artifact must resolve to a PDF file")
    return resolved, input_artifact


def _engine_plan(request: SkillRequest, resolved: Mapping[str, Path]) -> dict[str, Any]:
    plan = deepcopy(request.parameters.get("plan"))
    if not isinstance(plan, dict) or not isinstance(plan.get("operations"), list):
        raise ValueError("parameters.plan.operations must be a non-empty array")
    if not plan["operations"]:
        raise ValueError("parameters.plan.operations must be a non-empty array")
    for operation in plan["operations"]:
        if not isinstance(operation, dict):
            raise ValueError("each plan operation must be an object")
        if "image_artifact_id" in operation:
            artifact_id = str(operation.pop("image_artifact_id"))
            if artifact_id not in resolved:
                raise ValueError(f"image_artifact_id is not present in files: {artifact_id}")
            operation["path"] = str(resolved[artifact_id])
        if "source_artifact_id" in operation:
            artifact_id = str(operation.pop("source_artifact_id"))
            if artifact_id not in resolved:
                raise ValueError(f"source_artifact_id is not present in files: {artifact_id}")
            operation["source"] = str(resolved[artifact_id])
        if ("path" in operation or "source" in operation) and not request.context.get(
            "allow_local_paths", False
        ):
            allowed_paths = {str(path) for path in resolved.values()}
            for key in ("path", "source"):
                if key in operation and str(Path(operation[key]).resolve()) not in allowed_paths:
                    raise ValueError(
                        f"raw local {key} is not allowed; pass an Artifact reference instead"
                    )
    return plan


def _progress_message(item: Mapping[str, Any]) -> str:
    if item.get("message"):
        return str(item["message"])
    action = str(item.get("action", "PDF"))
    status = str(item.get("status", "working"))
    if action == "replace_text" and item.get("matches") is not None:
        return f"找到 {item['matches']} 处匹配，正在修改第 {item.get('page', '?')} 页"
    if item.get("page") is not None:
        return f"正在处理第 {item['page']} 页：{action} ({status})"
    return f"{action}: {status}"


def _progress_value(item: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(item.get("progress"), Mapping):
        return dict(item["progress"])
    current = item.get("operation")
    total = item.get("total_operations")
    if isinstance(current, int) and isinstance(total, int) and total > 0:
        return {
            "percent": round(current / total * 90, 2),
            "current": current,
            "total": total,
            "unit": "operation",
        }
    status_percent = {"analyzing": 5, "visual_validation": 95}
    return {"percent": status_percent.get(str(item.get("status")), 10)}


def _parse_progress(stderr: str) -> list[dict[str, Any]]:
    events = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _run_engine(
    python_executable: str,
    input_path: Path,
    output_path: Path,
    plan_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    environment = dict(os.environ)
    environment.update({"PDF_EDITOR_PROGRESS": "1", "PYTHONUTF8": "1"})
    process = subprocess.run(
        [
            python_executable,
            str(ENGINE),
            "apply",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--plan",
            str(plan_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=environment,
        check=False,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"PDF Editor returned invalid JSON (exit={process.returncode})"
        ) from exc
    progress = _parse_progress(process.stderr)
    if process.returncode != 0 or not result.get("ok"):
        code = str(result.get("code") or "PDF_EDITOR_EXECUTION_FAILED")
        message = str(result.get("error") or "PDF Editor execution failed")
        error = RuntimeError(message)
        error.code = code  # type: ignore[attr-defined]
        error.progress = progress  # type: ignore[attr-defined]
        raise error
    return result, progress


def _validation_passed(validation: Mapping[str, Any]) -> bool:
    required = (
        "operation_execution_ok",
        "reopen_ok",
        "semantic_ok",
        "visual_ok",
        "geometry_layout_ok",
    )
    return all(validation.get(key) is True for key in required)


def execute(
    request: SkillRequest,
    *,
    resolve_artifact: ArtifactResolver,
    publish_artifact: ArtifactPublisher,
    python_executable: str | None = None,
) -> SkillResult:
    """Execute one standard PDF Editor request without a Runtime dependency."""

    if request.skill_id != "pdf-editor":
        raise ValueError("SkillRequest.skill_id must be 'pdf-editor'")
    command = str(request.parameters.get("command", "apply"))
    if command != "apply":
        raise ValueError("The V1.2 Contract adapter currently supports command='apply'")

    builder = _EventBuilder(request)
    events = [
        builder.create(
            StreamEventType.TOOL_START,
            builder.tool_payload(command, input_summary=f"处理 {len(request.files)} 个输入文件"),
        )
    ]
    try:
        resolved, input_artifact = _resolve_files(request, resolve_artifact)
        plan = _engine_plan(request, resolved)
        output_name = Path(
            str(request.parameters.get("output_name") or "pdf-editor-output.pdf")
        ).name
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"
        with tempfile.TemporaryDirectory(prefix="pdf-editor-contract-") as directory:
            temp_dir = Path(directory)
            plan_path = temp_dir / "plan.json"
            output_path = temp_dir / output_name
            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result, raw_progress = _run_engine(
                python_executable or sys.executable,
                resolved[input_artifact.id],
                output_path,
                plan_path,
            )
            last_percent = 0.0
            for item in raw_progress:
                if item.get("event") != "tool.progress":
                    continue
                progress = _progress_value(item)
                percent = float(progress.get("percent", last_percent))
                percent = max(last_percent, min(99.0, percent))
                progress["percent"] = percent
                last_percent = percent
                events.append(
                    builder.create(
                        StreamEventType.TOOL_PROGRESS,
                        builder.tool_payload(
                            str(item.get("action") or command),
                            progress=progress,
                            message=_progress_message(item),
                        ),
                    )
                )

            validation = result.get("validation", {})
            if not isinstance(validation, Mapping) or not _validation_passed(validation):
                raise RuntimeError(f"PDF Editor PASS contract failed: {validation}")
            artifact = publish_artifact(output_path)
            if not isinstance(artifact, Artifact):
                raise TypeError("publish_artifact must return an Artifact")
            events.append(
                builder.create(
                    StreamEventType.FILE_CREATED,
                    builder.tool_payload(command, artifact=artifact.to_dict()),
                )
            )
            events.append(
                builder.create(
                    StreamEventType.TOOL_RESULT,
                    builder.tool_payload(
                        command,
                        status="succeeded",
                        summary="PDF 编辑与五层验收完成",
                        artifact_ids=[artifact.id],
                    ),
                )
            )
            return SkillResult(
                request_id=request.request_id,
                success=True,
                message="PDF 编辑完成",
                artifacts=(artifact,),
                events=tuple(events),
                validation=dict(validation),
            )
    except Exception as exc:
        last_percent = 0.0
        for item in getattr(exc, "progress", []):
            if item.get("event") != "tool.progress":
                continue
            progress = _progress_value(item)
            percent = float(progress.get("percent", last_percent))
            percent = max(last_percent, min(99.0, percent))
            progress["percent"] = percent
            last_percent = percent
            events.append(
                builder.create(
                    StreamEventType.TOOL_PROGRESS,
                    builder.tool_payload(
                        str(item.get("action") or command),
                        progress=progress,
                        message=_progress_message(item),
                    ),
                )
            )
        code = str(getattr(exc, "code", "PDF_EDITOR_CONTRACT_ERROR"))
        error = {
            "code": code,
            "message": str(exc),
            "retryable": False,
            "category": "validation" if "VALIDATION" in code or "FONT" in code else "internal",
        }
        events.append(
            builder.create(
                StreamEventType.TOOL_ERROR,
                builder.tool_payload(command, error=error),
            )
        )
        return SkillResult(
            request_id=request.request_id,
            success=False,
            message=str(exc),
            artifacts=(),
            events=tuple(events),
            validation={},
            error=error,
        )


def _local_resolver(mapping: Mapping[str, str]) -> ArtifactResolver:
    def resolve(artifact: Artifact) -> Path:
        value = mapping.get(artifact.id, mapping.get(artifact.uri))
        if value is None:
            raise KeyError(f"No local mapping for Artifact {artifact.id}")
        return Path(value)

    return resolve


def _local_publisher(output_dir: Path) -> ArtifactPublisher:
    output_dir.mkdir(parents=True, exist_ok=True)

    def publish(path: Path) -> Artifact:
        target = output_dir / path.name
        shutil.copy2(path, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return Artifact(
            id=f"art_{digest[:16]}",
            kind=ArtifactKind.FILE,
            name=target.name,
            mime_type="application/pdf",
            size_bytes=target.stat().st_size,
            uri=f"artifact://outputs/{target.name}",
            sha256=digest,
        )

    return publish


def main() -> None:
    parser = argparse.ArgumentParser(description="Local PDF Editor Contract adapter")
    parser.add_argument("--request", required=True)
    parser.add_argument("--artifact-map", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    request = SkillRequest.from_dict(json.loads(Path(args.request).read_text(encoding="utf-8")))
    mapping = json.loads(Path(args.artifact_map).read_text(encoding="utf-8"))
    result = execute(
        request,
        resolve_artifact=_local_resolver(mapping),
        publish_artifact=_local_publisher(Path(args.output_dir)),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if not result.success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
