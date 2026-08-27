"""rembg adapter with a small u2netp default and explicit model cache."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import RuntimePaths, model_download_allowed
from .errors import RuntimeExecutionError, RuntimeUnavailableError


SUPPORTED_MODELS = {
    "u2netp": "u2netp.onnx",
    "u2net": "u2net.onnx",
    "isnet-general-use": "isnet-general-use.onnx",
}


@dataclass(frozen=True)
class RembgConfig:
    model: str
    model_dir: Path
    allow_download: bool

    @classmethod
    def from_env(cls, request: Mapping[str, Any] | None = None) -> "RembgConfig":
        request = request or {}
        paths = RuntimePaths.from_env()
        model = str(request.get("model") or os.environ.get("QWENPAW_REMBG_MODEL") or "u2netp")
        if model not in SUPPORTED_MODELS:
            raise RuntimeUnavailableError(
                "rembg model must be u2netp, u2net or isnet-general-use; large models are never selected implicitly"
            )
        return cls(model=model, model_dir=paths.rembg_models, allow_download=model_download_allowed())

    @property
    def model_file(self) -> Path:
        return self.model_dir / SUPPORTED_MODELS[self.model]

    def model_is_accessible(self) -> bool:
        return self.model_file.is_file() or self.allow_download


class RembgAdapter:
    engine = "rembg"

    def __init__(
        self,
        config: RembgConfig | None = None,
        *,
        session_factory: Callable[..., Any] | None = None,
        remove_function: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or RembgConfig.from_env()
        self._session_factory = session_factory
        self._remove_function = remove_function
        self._session: Any | None = None

    @classmethod
    def from_request(cls, request: Mapping[str, Any] | None = None) -> "RembgAdapter":
        return cls(RembgConfig.from_env(request))

    def _functions(self) -> tuple[Callable[..., Any], Callable[..., Any]]:
        if self._session_factory is not None and self._remove_function is not None:
            return self._session_factory, self._remove_function
        try:
            from rembg import new_session, remove
        except ImportError as exc:
            raise RuntimeUnavailableError("rembg is not installed") from exc
        return self._session_factory or new_session, self._remove_function or remove

    def load_session(self) -> Any:
        if self._session is not None:
            return self._session
        if not self.config.model_is_accessible():
            raise RuntimeUnavailableError(
                f"rembg model is not available at {self.config.model_file}; pre-populate the workspace cache"
            )
        self.config.model_dir.mkdir(parents=True, exist_ok=True)
        session_factory, _remove = self._functions()
        try:
            self._session = session_factory(
                self.config.model,
                u2net_home=str(self.config.model_dir),
            )
        except Exception as exc:
            raise RuntimeExecutionError(f"rembg session load failed: {exc}") from exc
        return self._session

    def segment(
        self,
        image: Path,
        output: Path,
        *,
        alpha_matting: bool = False,
    ) -> Mapping[str, Any]:
        if not image.is_file():
            raise RuntimeUnavailableError(f"image file does not exist: {image}")
        _session_factory, remove = self._functions()
        try:
            content = remove(
                image.read_bytes(),
                session=self.load_session(),
                alpha_matting=alpha_matting,
            )
            if not isinstance(content, (bytes, bytearray)):
                buffer = BytesIO()
                content.save(buffer, format="PNG")
                content = buffer.getvalue()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(bytes(content))
            from PIL import Image

            with Image.open(output) as rendered:
                rendered.load()
                if "A" not in rendered.getbands():
                    raise RuntimeExecutionError("rembg output does not contain an alpha channel")
                width, height = rendered.size
        except (RuntimeUnavailableError, RuntimeExecutionError):
            raise
        except Exception as exc:
            raise RuntimeExecutionError(f"rembg inference failed: {exc}") from exc
        return {
            "engine": self.engine,
            "model": self.config.model,
            "alpha_matting": alpha_matting,
            "width": width,
            "height": height,
        }

    def healthcheck(self, *, runtime_test: bool = False) -> dict[str, Any]:
        if not self.config.model_is_accessible():
            return {"status": "DEGRADED", "runtime_test": "model_missing", "error": "model not accessible"}
        if not runtime_test:
            return {"status": "AVAILABLE", "runtime_test": "model_accessible", "error": None}
        try:
            from PIL import Image

            source = BytesIO()
            Image.new("RGB", (2, 2), "white").save(source, format="PNG")
            _session_factory, remove = self._functions()
            output = remove(source.getvalue(), session=self.load_session(), alpha_matting=False)
            if not output:
                raise RuntimeExecutionError("rembg returned an empty result")
        except RuntimeUnavailableError as exc:
            return {"status": "DEGRADED", "runtime_test": "model_missing", "error": str(exc)}
        except Exception as exc:
            return {"status": "RUNTIME_ERROR", "runtime_test": "failed", "error": str(exc)}
        return {"status": "AVAILABLE", "runtime_test": "inference_pass", "error": None}
