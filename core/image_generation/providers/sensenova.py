"""SenseNova image-generation provider recovered without Hermes dependencies.

Protocol compatibility follows the public OpenSenseNova ``sn-image-base``
implementation: Bearer auth, ``POST /images/generations``, OpenAI-style image
responses, local download, and validation. A bounded task polling path is also
accepted for gateways that return ``task_id`` instead of image data.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image

from ..contracts import (
    GeneratedImage,
    GenerationStatus,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from ..provider import ImageGenerationProvider, ProgressCallback


DEFAULT_BASE_URL = "https://token.sensenova.cn/v1"
DEFAULT_MODEL = "sensenova-u1-fast"


class TransportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SenseNovaTransport(Protocol):
    def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout: float,
    ) -> Mapping[str, Any]:
        ...

    def get_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
    ) -> Mapping[str, Any]:
        ...

    def get_bytes(self, url: str, *, timeout: float) -> tuple[bytes, str | None]:
        ...


class UrllibSenseNovaTransport:
    """Standard-library HTTP transport; injectable in tests and deployments."""

    def post_json(self, url, *, headers, payload, timeout):
        body = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=dict(headers), method="POST")
        return self._json_response(request, timeout)

    def get_json(self, url, *, headers, timeout):
        request = Request(url, headers=dict(headers), method="GET")
        return self._json_response(request, timeout)

    def get_bytes(self, url, *, timeout):
        request = Request(url, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read(), response.headers.get_content_type()
        except HTTPError as exc:
            raise TransportError(
                f"HTTP {exc.code} while downloading generated image",
                status_code=exc.code,
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TransportError(str(exc)) from exc

    @staticmethod
    def _json_response(request: Request, timeout: float) -> Mapping[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise TransportError(
                f"HTTP {exc.code}: {detail}", status_code=exc.code
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise TransportError(str(exc)) from exc
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("SenseNova returned invalid JSON") from exc
        if not isinstance(decoded, Mapping):
            raise TransportError("SenseNova JSON response must be an object")
        return decoded


@dataclass(frozen=True, slots=True)
class SenseNovaConfig:
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    poll_interval: float = 5.0
    timeout: float = 300.0
    max_retries: int = 1
    status_url_template: str = ""

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SENSENOVA_BASE_URL must be an absolute HTTP(S) URL")
        if not self.model.strip():
            raise ValueError("SENSENOVA_IMAGE_MODEL must be non-empty")
        if self.poll_interval <= 0 or self.timeout <= 0:
            raise ValueError("poll_interval and timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "SenseNovaConfig":
        env = os.environ if environ is None else environ
        return cls(
            api_key=(
                env.get("SENSENOVA_API_KEY")
                or env.get("SN_IMAGE_GEN_API_KEY")
                or env.get("SN_API_KEY")
                or ""
            ),
            base_url=(
                env.get("SENSENOVA_BASE_URL")
                or env.get("SN_IMAGE_GEN_BASE_URL")
                or env.get("SN_BASE_URL")
                or DEFAULT_BASE_URL
            ),
            model=(
                env.get("SENSENOVA_IMAGE_MODEL")
                or env.get("SN_IMAGE_GEN_MODEL")
                or DEFAULT_MODEL
            ),
            poll_interval=float(env.get("SENSENOVA_POLL_INTERVAL", "5")),
            timeout=float(env.get("SENSENOVA_TIMEOUT", "300")),
            max_retries=int(env.get("SENSENOVA_MAX_RETRIES", "1")),
            status_url_template=env.get("SENSENOVA_STATUS_URL_TEMPLATE", ""),
        )


class SenseNovaImageProvider(ImageGenerationProvider):
    def __init__(
        self,
        *,
        config: SenseNovaConfig | None = None,
        transport: SenseNovaTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or SenseNovaConfig.from_env()
        self.transport = transport or UrllibSenseNovaTransport()
        self._sleep = sleep
        self._clock = clock

    @property
    def name(self) -> str:
        return "sensenova"

    def generate(self, request, *, output_dir, progress=None):
        started = self._clock()
        model = request.model or self.config.model
        size_plan = request.size_plan
        if not self.config.api_key:
            return self._failure(
                GenerationStatus.PROVIDER_NOT_CONFIGURED,
                request,
                model,
                started,
                "SENSENOVA_API_KEY is not configured",
                "PROVIDER_NOT_CONFIGURED",
            )
        self._emit(progress, GenerationStatus.SUBMITTED, "正在提交图片生成任务")
        payload = self._payload(request, model)
        try:
            data = self._retry(
                lambda: self.transport.post_json(
                    self._submit_url(),
                    headers=self._headers(),
                    payload=payload,
                    timeout=self.config.timeout,
                )
            )
            task_id = self._task_id(data)
            sources = self._sources(data)
            if task_id and not sources:
                data = self._poll(task_id, progress=progress)
                if data is None:
                    return self._failure(
                        GenerationStatus.TIMEOUT,
                        request,
                        model,
                        started,
                        "SenseNova image generation timed out",
                        "TIMEOUT",
                        task_id=task_id,
                        retryable=True,
                    )
                if self._state(data) == "FAILED":
                    return self._failure(
                        GenerationStatus.FAILED,
                        request,
                        model,
                        started,
                        self._error_message(data) or "SenseNova generation failed",
                        "PROVIDER_FAILED",
                        task_id=task_id,
                    )
                sources = self._sources(data)
            if not sources:
                return self._failure(
                    GenerationStatus.FAILED,
                    request,
                    model,
                    started,
                    "SenseNova returned no image data",
                    "EMPTY_RESPONSE",
                    task_id=task_id,
                )
            self._emit(progress, GenerationStatus.RUNNING, "正在生成图片")
            images = tuple(
                self._materialize(
                    source,
                    output_dir=Path(output_dir),
                    seed=source.get("seed", request.seed),
                    index=index,
                    size_plan=size_plan,
                )
                for index, source in enumerate(sources[: request.count])
            )
        except TransportError as exc:
            code = (
                "AUTH_FAILED"
                if exc.status_code in {401, 403}
                else "PROVIDER_REQUEST_FAILED"
            )
            return self._failure(
                GenerationStatus.FAILED,
                request,
                model,
                started,
                str(exc),
                code,
                retryable=(
                    exc.status_code is None
                    or exc.status_code == 429
                    or bool(exc.status_code and exc.status_code >= 500)
                ),
            )
        except (OSError, ValueError, TypeError) as exc:
            return self._failure(
                GenerationStatus.FAILED,
                request,
                model,
                started,
                str(exc),
                "INVALID_IMAGE" if isinstance(exc, ValueError) else "OUTPUT_FAILED",
            )
        self._emit(progress, GenerationStatus.SUCCESS, "图片生成完成")
        return ImageGenerationResponse(
            status=GenerationStatus.SUCCESS,
            images=images,
            provider=self.name,
            model=model,
            seed=request.seed,
            duration=round(self._clock() - started, 3),
            task_id=task_id,
            requested_size=size_plan.requested_size,
            requested_aspect_ratio=size_plan.requested_aspect_ratio,
            image_size=size_plan.image_size,
            provider_size=(
                images[0].provider_size if images else size_plan.provider_size
            ),
            provider_aspect_ratio=size_plan.provider_aspect_ratio,
            final_size=images[0].final_size if images else size_plan.final_size,
            retryable=False,
        )

    def _submit_url(self) -> str:
        base = self.config.base_url.rstrip("/")
        return base if base.endswith("/images/generations") else f"{base}/images/generations"

    def _status_url(self, task_id: str) -> str:
        if self.config.status_url_template:
            return self.config.status_url_template.format(task_id=task_id)
        return f"{self._submit_url().rstrip('/')}/{task_id}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _payload(request: ImageGenerationRequest, model: str) -> dict[str, Any]:
        size_plan = request.size_plan
        payload: dict[str, Any] = {
            "model": model,
            "prompt": request.prompt,
            "size": size_plan.provider_size,
            "n": request.count,
            "response_format": "url",
            "output_format": "png",
            "watermark": False,
        }
        if request.negative_prompt:
            payload["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            payload["seed"] = request.seed
        return payload

    def _retry(self, operation):
        last_error: TransportError | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return operation()
            except TransportError as exc:
                last_error = exc
                retryable = exc.status_code is None or exc.status_code == 429 or (
                    exc.status_code >= 500
                )
                if not retryable or attempt >= self.config.max_retries:
                    raise
                self._sleep(min(2.0**attempt, 5.0))
        assert last_error is not None
        raise last_error

    def _poll(self, task_id: str, *, progress: ProgressCallback | None):
        deadline = self._clock() + self.config.timeout
        self._emit(progress, GenerationStatus.RUNNING, "正在生成图片")
        while self._clock() < deadline:
            data = self._retry(
                lambda: self.transport.get_json(
                    self._status_url(task_id),
                    headers=self._headers(),
                    timeout=self.config.timeout,
                )
            )
            state = self._state(data)
            if state in {"SUCCESS", "FAILED"} or self._sources(data):
                return data
            self._sleep(self.config.poll_interval)
        return None

    def _materialize(self, source, *, output_dir, seed, index, size_plan):
        if source.get("url"):
            data, declared_mime = self._retry(
                lambda: self.transport.get_bytes(
                    str(source["url"]), timeout=self.config.timeout
                )
            )
            source_url = str(source["url"])
        elif source.get("b64_json"):
            try:
                data = base64.b64decode(str(source["b64_json"]), validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError("SenseNova returned invalid base64 image data") from exc
            declared_mime = None
            source_url = None
        else:
            raise ValueError("SenseNova image result has no URL or base64 data")
        mime_type, extension, width, height = self._validate_image(data)
        if declared_mime and declared_mime not in {
            "application/octet-stream",
            mime_type,
        }:
            raise ValueError("downloaded image MIME type does not match its content")
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"sensenova_{uuid4().hex}_{index + 1}{extension}"
        target = output_dir / filename
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_dir, prefix=f".{filename}.", suffix=".tmp", delete=False
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path.replace(target)
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise
        return GeneratedImage(
            path=target.resolve(),
            filename=filename,
            mime_type=mime_type,
            width=width,
            height=height,
            seed=seed if isinstance(seed, int) else None,
            source_url=source_url,
            requested_size=size_plan.requested_size,
            requested_aspect_ratio=size_plan.requested_aspect_ratio,
            image_size=size_plan.image_size,
            provider_size=f"{width}x{height}",
            provider_aspect_ratio=size_plan.provider_aspect_ratio,
            final_size=f"{width}x{height}",
        )

    @staticmethod
    def _validate_image(data: bytes) -> tuple[str, str, int, int]:
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                fmt = (image.format or "").upper()
                width, height = image.size
        except Exception as exc:
            raise ValueError("downloaded payload is not a valid image") from exc
        formats = {
            "PNG": ("image/png", ".png"),
            "JPEG": ("image/jpeg", ".jpg"),
        }
        if fmt not in formats:
            raise ValueError(f"unsupported generated image format: {fmt or 'unknown'}")
        mime_type, extension = formats[fmt]
        return mime_type, extension, width, height

    @staticmethod
    def _sources(data: Mapping[str, Any]) -> list[dict[str, Any]]:
        candidates = data.get("data") or data.get("images") or []
        if isinstance(candidates, Mapping):
            candidates = [candidates]
        result: list[dict[str, Any]] = []
        if isinstance(candidates, list):
            for item in candidates:
                if not isinstance(item, Mapping):
                    continue
                url = item.get("url") or item.get("raw") or item.get("img_url")
                b64_json = item.get("b64_json")
                if url or b64_json:
                    result.append(
                        {
                            "url": url,
                            "b64_json": b64_json,
                            "seed": item.get("seed"),
                        }
                    )
        return result

    @staticmethod
    def _task_id(data: Mapping[str, Any]) -> str | None:
        value = data.get("task_id") or data.get("id")
        return str(value) if value else None

    @staticmethod
    def _state(data: Mapping[str, Any]) -> str:
        value = data.get("status") or data.get("state") or ""
        if isinstance(value, int):
            return "SUCCESS" if value == 1 else "RUNNING"
        value = str(value).upper()
        return "RUNNING" if value in {"PENDING", "SUBMITTED", "PROCESSING"} else value

    @staticmethod
    def _error_message(data: Mapping[str, Any]) -> str:
        value = data.get("error") or data.get("message") or data.get("state_message")
        return str(value) if value else ""

    @staticmethod
    def _emit(progress, status, message):
        if progress is not None:
            progress(status, message)

    def _failure(
        self,
        status,
        request,
        model,
        started,
        error,
        error_code,
        *,
        task_id=None,
        retryable=False,
    ):
        size_plan = request.size_plan
        return ImageGenerationResponse(
            status=status,
            provider=self.name,
            model=model,
            seed=request.seed,
            duration=round(max(0.0, self._clock() - started), 3),
            error=error,
            error_code=error_code,
            task_id=task_id,
            requested_size=size_plan.requested_size,
            requested_aspect_ratio=size_plan.requested_aspect_ratio,
            image_size=size_plan.image_size,
            provider_size=size_plan.provider_size,
            provider_aspect_ratio=size_plan.provider_aspect_ratio,
            final_size=size_plan.final_size,
            retryable=retryable,
        )
