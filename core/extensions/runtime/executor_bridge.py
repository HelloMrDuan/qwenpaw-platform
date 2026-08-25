"""Allowlisted loader for the existing PDF Editor Skill executor."""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.contracts import SkillRequest, SkillResult
from core.extensions import (
    ExtensionMetadata,
    ExtensionRegistry,
    ExtensionRuntime,
    ExtensionType,
)

from .models import ArtifactPublisher, ArtifactResolver, SkillExecutorDescriptor


ALLOWED_SKILL_ID = "pdf-editor"
ALLOWED_EXECUTOR_PATH = "executor/main.py"
ALLOWED_CALLABLE = "execute"


class UnsupportedSkillExecutor(ValueError):
    """Raised when a request falls outside the Phase 7.0 PDF allowlist."""


class ExecutorLoadError(RuntimeError):
    """Raised when the declared existing executor cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class _LoadedExecutor:
    descriptor: SkillExecutorDescriptor
    callable: Callable[..., SkillResult]


class ExtensionExecutorBridge:
    """Resolve and call only the existing PDF Editor contract executor."""

    def __init__(
        self,
        repository_root: str | Path,
        registry: ExtensionRegistry,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.registry = registry
        self._cache: dict[tuple[str, str], _LoadedExecutor] = {}

    def describe(self, skill_id: str) -> SkillExecutorDescriptor:
        return self._resolve_descriptor(self._metadata(skill_id))

    def execute(
        self,
        request: SkillRequest,
        *,
        resolve_artifact: ArtifactResolver,
        publish_artifact: ArtifactPublisher,
        python_executable: str | None = None,
    ) -> tuple[SkillExecutorDescriptor, SkillResult]:
        if not isinstance(request, SkillRequest):
            raise TypeError("request must be a SkillRequest")
        loaded = self._load(request.skill_id)
        kwargs = {
            "resolve_artifact": resolve_artifact,
            "publish_artifact": publish_artifact,
        }
        if python_executable is not None:
            kwargs["python_executable"] = python_executable
        try:
            result = loaded.callable(request, **kwargs)
        except Exception as exc:
            raise ExecutorLoadError(
                f"Skill executor call failed before returning SkillResult: {exc}"
            ) from exc
        if not isinstance(result, SkillResult):
            raise ExecutorLoadError("Skill executor must return a SkillResult")
        return loaded.descriptor, result

    def _load(self, skill_id: str) -> _LoadedExecutor:
        metadata = self._metadata(skill_id)
        cache_key = (metadata.name, metadata.version)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        descriptor = self._resolve_descriptor(metadata)
        module_name = "qwenpaw_extension_" + re.sub(
            r"[^A-Za-z0-9_]", "_", f"{metadata.name}_{metadata.version}"
        )
        spec = importlib.util.spec_from_file_location(module_name, descriptor.executor_path)
        if spec is None or spec.loader is None:
            raise ExecutorLoadError(
                f"cannot create module spec for: {descriptor.executor_path}"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise ExecutorLoadError(
                f"cannot load existing Skill executor: {descriptor.executor_path}"
            ) from exc
        executor = getattr(module, descriptor.callable_name, None)
        if not callable(executor):
            raise ExecutorLoadError(
                f"declared callable not found: {descriptor.callable_name}"
            )
        self._validate_signature(executor)
        loaded = _LoadedExecutor(descriptor=descriptor, callable=executor)
        self._cache[cache_key] = loaded
        return loaded

    def _metadata(self, skill_id: str) -> ExtensionMetadata:
        if skill_id != ALLOWED_SKILL_ID:
            raise UnsupportedSkillExecutor(
                "Phase 7.0 only permits the existing pdf-editor executor"
            )
        metadata = self.registry.get(skill_id)
        if metadata is None:
            raise UnsupportedSkillExecutor(f"Skill is not registered: {skill_id}")
        if metadata.type is not ExtensionType.SKILL:
            raise UnsupportedSkillExecutor(f"Extension is not a Skill: {skill_id}")
        return metadata

    def _resolve_descriptor(
        self, metadata: ExtensionMetadata
    ) -> SkillExecutorDescriptor:
        executor = metadata.executor
        expected_declaration = {
            "runtime": ExtensionRuntime.PYTHON.value,
            "path": ALLOWED_EXECUTOR_PATH,
            "callable": ALLOWED_CALLABLE,
        }
        if executor is None or dict(executor) != expected_declaration:
            raise UnsupportedSkillExecutor(
                "pdf-editor executor declaration is outside the Phase 7.0 allowlist"
            )
        skill_root = (self.repository_root / "skills" / ALLOWED_SKILL_ID).resolve()
        manifest_path = skill_root / "manifest.yaml"
        executor_path = (skill_root / Path(*Path(ALLOWED_EXECUTOR_PATH).parts)).resolve()
        expected_path = (skill_root / "executor" / "main.py").resolve()
        if executor_path != expected_path or not executor_path.is_relative_to(skill_root):
            raise UnsupportedSkillExecutor("pdf-editor executor path is not allowed")
        return SkillExecutorDescriptor(
            name=metadata.name,
            version=metadata.version,
            type=metadata.type,
            runtime=metadata.runtime,
            manifest_path=manifest_path,
            executor_path=executor_path,
            callable_name=ALLOWED_CALLABLE,
            declared_events=tuple(metadata.events),
            artifact_contract=dict(metadata.artifacts),
        )

    @staticmethod
    def _validate_signature(executor: Callable[..., SkillResult]) -> None:
        parameters = inspect.signature(executor).parameters
        required_names = {"request", "resolve_artifact", "publish_artifact"}
        if not required_names.issubset(parameters):
            raise ExecutorLoadError(
                "Skill executor signature must accept request, resolve_artifact, "
                "and publish_artifact"
            )
