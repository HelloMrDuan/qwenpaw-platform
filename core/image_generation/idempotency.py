"""Durable, checksum-verified idempotency for paid image generation calls."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Iterator, Mapping


_LOCKS_GUARD = Lock()
_LOCKS: dict[str, RLock] = {}


class ImageGenerationIdempotencyStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    @staticmethod
    def fingerprint(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def keys(
        self,
        *,
        fingerprint: str,
        tool_call_id: str | None,
        request_id: str | None,
    ) -> tuple[str, ...]:
        keys: list[str] = []
        if tool_call_id:
            keys.append(f"tool-call:{tool_call_id}")
        if request_id:
            keys.append(f"request:{request_id}:{fingerprint}")
        return tuple(keys)

    @contextmanager
    def locked(self, keys: tuple[str, ...]) -> Iterator[None]:
        lock_key = keys[-1] if keys else "unscoped"
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(lock_key, RLock())
        with lock:
            yield

    def load(self, keys: tuple[str, ...]) -> dict[str, Any] | None:
        for key in keys:
            path = self._path(key)
            if not path.is_file():
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and self._valid(value):
                result = deepcopy(value)
                metadata = dict(result.get("metadata") or {})
                metadata.update({"idempotency_hit": True, "idempotency_key": key})
                result["metadata"] = metadata
                return result
        return None

    def save(self, keys: tuple[str, ...], result: Mapping[str, Any]) -> None:
        if not keys:
            return
        status = str(result.get("status") or "")
        retryable = bool(result.get("retryable"))
        if status != "SUCCESS" and retryable:
            return
        payload = deepcopy(dict(result))
        metadata = dict(payload.get("metadata") or {})
        metadata.update({"idempotency_hit": False})
        payload["metadata"] = metadata
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        self.root.mkdir(parents=True, exist_ok=True)
        for key in keys:
            target = self._path(key)
            temporary = target.with_suffix(".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(target)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    @staticmethod
    def _valid(result: Mapping[str, Any]) -> bool:
        if str(result.get("status")) != "SUCCESS":
            return not bool(result.get("retryable"))
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                return False
            metadata = artifact.get("metadata")
            if not isinstance(metadata, Mapping):
                return False
            path_value = metadata.get("path")
            expected = artifact.get("sha256")
            if not path_value or not expected:
                return False
            path = Path(str(path_value))
            if not path.is_file() or _sha256(path) != expected:
                return False
        return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
