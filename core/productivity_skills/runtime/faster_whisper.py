"""Faster Whisper adapter with normalized transcript output."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import RuntimePaths, model_download_allowed
from .errors import RuntimeExecutionError, RuntimeUnavailableError


SUPPORTED_MODELS = {"tiny", "base", "small"}


@dataclass(frozen=True)
class FasterWhisperConfig:
    model: str
    model_path: Path | None
    cache_dir: Path
    device: str
    compute_type: str
    allow_download: bool
    workspace_cache_dir: Path | None = None
    discovery_dirs: tuple[Path, ...] = ()

    @classmethod
    def from_env(cls, request: Mapping[str, Any] | None = None) -> "FasterWhisperConfig":
        request = request or {}
        paths = RuntimePaths.from_env()
        raw_path = request.get("model_path") or os.environ.get("QWENPAW_ASR_MODEL_PATH")
        model_path = Path(str(raw_path)).expanduser() if raw_path else None
        model = str(request.get("model") or os.environ.get("QWENPAW_ASR_MODEL") or "tiny")
        if model_path is None and model not in SUPPORTED_MODELS:
            raise RuntimeUnavailableError(
                "QWENPAW_ASR_MODEL must be tiny, base or small unless QWENPAW_ASR_MODEL_PATH is set"
            )
        return cls(
            model=model,
            model_path=model_path,
            cache_dir=paths.configured_asr_cache or paths.asr_models,
            device=str(request.get("device") or os.environ.get("QWENPAW_ASR_DEVICE") or "auto"),
            compute_type=str(
                request.get("compute_type")
                or os.environ.get("QWENPAW_ASR_COMPUTE_TYPE")
                or "int8"
            ),
            allow_download=model_download_allowed(),
            workspace_cache_dir=paths.asr_models,
            discovery_dirs=tuple(
                path
                for path in (
                    paths.asr_models,
                    paths.configured_asr_cache,
                    *paths.huggingface_caches,
                )
                if path is not None
            ),
        )

    @property
    def reference(self) -> str:
        discovered = self.discover_model()
        return str(discovered) if discovered else self.model

    @staticmethod
    def _valid_model_directory(path: Path) -> bool:
        return path.is_dir() and (path / "model.bin").is_file() and (path / "config.json").is_file()

    def _search_root(self, root: Path) -> Path | None:
        if self._valid_model_directory(root):
            return root
        direct = root / self.model
        if self._valid_model_directory(direct):
            return direct
        repository = root / f"models--Systran--faster-whisper-{self.model}" / "snapshots"
        if repository.is_dir():
            for snapshot in sorted(repository.iterdir()):
                if self._valid_model_directory(snapshot):
                    return snapshot
        if root.is_dir():
            pattern = f"models--Systran--faster-whisper-{self.model}/snapshots/*/model.bin"
            for model_file in sorted(root.glob(pattern)):
                if self._valid_model_directory(model_file.parent):
                    return model_file.parent
        return None

    def discover_model(self) -> Path | None:
        if self.model_path is not None:
            return self.model_path if self._valid_model_directory(self.model_path) else None
        roots = self.discovery_dirs or tuple(
            path
            for path in (self.workspace_cache_dir, self.cache_dir)
            if path is not None
        )
        seen = set()
        for root in roots:
            key = str(root.absolute()).casefold()
            if key in seen:
                continue
            seen.add(key)
            discovered = self._search_root(root)
            if discovered is not None:
                return discovered
        return None

    def model_is_accessible(self) -> bool:
        return self.discover_model() is not None or self.allow_download


class FasterWhisperAdapter:
    engine = "faster-whisper"

    def __init__(
        self,
        config: FasterWhisperConfig | None = None,
        *,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or FasterWhisperConfig.from_env()
        self._model_factory = model_factory
        self._model: Any | None = None

    @classmethod
    def from_request(cls, request: Mapping[str, Any] | None = None) -> "FasterWhisperAdapter":
        return cls(FasterWhisperConfig.from_env(request))

    def _factory(self) -> Callable[..., Any]:
        if self._model_factory is not None:
            return self._model_factory
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeUnavailableError("faster-whisper is not installed") from exc
        return WhisperModel

    def load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.config.model_is_accessible():
            raise RuntimeUnavailableError(
                "No local faster-whisper model is accessible; configure QWENPAW_ASR_MODEL_PATH "
                "or pre-populate QWENPAW_ASR_CACHE_DIR"
            )
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._model = self._factory()(
                self.config.reference,
                device=self.config.device,
                compute_type=self.config.compute_type,
                download_root=str(self.config.cache_dir),
                local_files_only=not self.config.allow_download,
            )
        except RuntimeUnavailableError:
            raise
        except Exception as exc:
            raise RuntimeExecutionError(f"faster-whisper model load failed: {exc}") from exc
        return self._model

    @staticmethod
    def _confidence(segment: Any) -> float | None:
        value = getattr(segment, "avg_logprob", None)
        if value is None:
            return None
        try:
            return round(max(0.0, min(1.0, math.exp(float(value)))), 6)
        except (TypeError, ValueError, OverflowError):
            return None

    def transcribe(
        self,
        media: Path,
        *,
        language: str | None = None,
        diarization: bool = False,
    ) -> Mapping[str, Any]:
        if not media.is_file():
            raise RuntimeUnavailableError(f"media file does not exist: {media}")
        if diarization:
            raise RuntimeUnavailableError("faster-whisper adapter does not provide speaker diarization")
        try:
            generated, info = self.load_model().transcribe(
                str(media),
                language=language or None,
                word_timestamps=False,
                vad_filter=True,
            )
            segments = []
            for item in generated:
                text = str(getattr(item, "text", "") or "").strip()
                segment = {
                    "start": round(float(getattr(item, "start", 0.0)), 3),
                    "end": round(float(getattr(item, "end", 0.0)), 3),
                    "text": text,
                }
                confidence = self._confidence(item)
                if confidence is not None:
                    segment["confidence"] = confidence
                no_speech = getattr(item, "no_speech_prob", None)
                if no_speech is not None:
                    segment["no_speech_probability"] = round(float(no_speech), 6)
                segments.append(segment)
        except (RuntimeUnavailableError, RuntimeExecutionError):
            raise
        except Exception as exc:
            raise RuntimeExecutionError(f"faster-whisper transcription failed: {exc}") from exc
        detected_language = str(language or getattr(info, "language", "") or "unknown")
        duration = float(
            getattr(info, "duration", 0.0)
            or max((item["end"] for item in segments), default=0.0)
        )
        return {
            "language": detected_language,
            "text": " ".join(item["text"] for item in segments if item["text"]).strip(),
            "segments": segments,
            "engine": self.engine,
            "model": self.config.model,
            "duration": round(duration, 3),
        }

    def healthcheck(self, *, load_model: bool = False) -> dict[str, Any]:
        accessible = self.config.model_is_accessible()
        if not accessible:
            return {"status": "DEGRADED", "runtime_test": "model_missing", "error": "model not accessible"}
        if load_model:
            try:
                self.load_model()
            except RuntimeUnavailableError as exc:
                return {"status": "DEGRADED", "runtime_test": "model_missing", "error": str(exc)}
            except RuntimeExecutionError as exc:
                return {"status": "RUNTIME_ERROR", "runtime_test": "failed", "error": str(exc)}
            return {"status": "AVAILABLE", "runtime_test": "model_load_pass", "error": None}
        return {"status": "AVAILABLE", "runtime_test": "model_accessible", "error": None}
