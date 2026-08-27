from __future__ import annotations

from collections import deque
from io import BytesIO
from typing import Any, Mapping

from PIL import Image


def image_bytes(fmt: str = "PNG", size: tuple[int, int] = (32, 24)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (40, 80, 120)).save(buffer, format=fmt)
    return buffer.getvalue()


class FakeTransport:
    def __init__(
        self,
        *,
        post: Mapping[str, Any] | Exception,
        polls: list[Mapping[str, Any] | Exception] | None = None,
        downloads: Mapping[str, tuple[bytes, str | None] | Exception] | None = None,
    ) -> None:
        self.post_result = post
        self.polls = deque(polls or [])
        self.downloads = dict(downloads or {})
        self.post_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []
        self.download_calls: list[str] = []

    def post_json(self, url, *, headers, payload, timeout):
        self.post_calls.append(
            {"url": url, "headers": dict(headers), "payload": dict(payload), "timeout": timeout}
        )
        if isinstance(self.post_result, Exception):
            raise self.post_result
        return self.post_result

    def get_json(self, url, *, headers, timeout):
        self.get_calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
        if not self.polls:
            raise AssertionError("unexpected polling request")
        result = self.polls.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    def get_bytes(self, url, *, timeout):
        self.download_calls.append(url)
        result = self.downloads[url]
        if isinstance(result, Exception):
            raise result
        return result


class IncrementingClock:
    def __init__(self, *, step: float = 1.0) -> None:
        self.value = -step
        self.step = step

    def __call__(self) -> float:
        self.value += self.step
        return self.value
