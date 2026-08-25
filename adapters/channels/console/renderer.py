"""Render transport-neutral outputs to a text stream."""

from __future__ import annotations

import sys
from threading import RLock
from typing import TextIO

from core.contracts import Artifact, RenderedOutput, RenderedOutputType


class ConsoleOutputWriter:
    """Write RenderedOutput objects without owning a terminal or event loop."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        if not hasattr(self.stream, "write") or not hasattr(self.stream, "flush"):
            raise TypeError("stream must provide write() and flush()")
        self._line_open = False
        self._lock = RLock()

    def write(self, output: RenderedOutput) -> None:
        if not isinstance(output, RenderedOutput):
            raise TypeError("output must be a RenderedOutput")
        with self._lock:
            if output.type is RenderedOutputType.TEXT_DELTA:
                self._write_delta(output.text or "")
            elif output.type is RenderedOutputType.MESSAGE:
                self._write_line(output.text or "")
            elif output.type is RenderedOutputType.MESSAGE_UPDATE:
                self._write_line(f"[update] {output.text or ''}")
            elif output.type is RenderedOutputType.STATUS:
                self._write_line(f"[status] {output.text or ''}")
            elif output.type is RenderedOutputType.FILE:
                self._write_artifact(output.artifact)
            elif output.type is RenderedOutputType.ERROR:
                self._write_line(f"[error] {output.text or '执行失败'}")
            else:  # defensive guard for future enum additions
                raise ValueError(f"unsupported rendered output type: {output.type}")
            self.stream.flush()

    def write_message(self, message: str) -> None:
        if not isinstance(message, str) or not message:
            raise ValueError("message must be a non-empty string")
        with self._lock:
            self._write_line(message)
            self.stream.flush()

    def write_artifact(self, artifact: Artifact) -> None:
        if not isinstance(artifact, Artifact):
            raise TypeError("artifact must be an Artifact")
        with self._lock:
            self._write_artifact(artifact)
            self.stream.flush()

    def close_line(self) -> None:
        with self._lock:
            if self._line_open:
                self.stream.write("\n")
                self._line_open = False
                self.stream.flush()

    def _write_delta(self, text: str) -> None:
        self.stream.write(text)
        self._line_open = bool(text) and not text.endswith("\n")

    def _write_line(self, text: str) -> None:
        if self._line_open:
            self.stream.write("\n")
        self.stream.write(f"{text}\n")
        self._line_open = False

    def _write_artifact(self, artifact: Artifact | None) -> None:
        if artifact is None:
            raise ValueError("file output requires an Artifact")
        self._write_line(f"[file] {artifact.name} ({artifact.uri})")
