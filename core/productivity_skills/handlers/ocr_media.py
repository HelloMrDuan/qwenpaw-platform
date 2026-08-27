"""OCR and media transcription handlers with explicit Runtime degradation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from ..artifacts import artifact, safe_output_path, write_report
from ..capabilities import CapabilityResolver
from ..models import SkillStatus, invalid, result
from ..runtime import (
    RuntimeExecutionError,
    RuntimeUnavailableError,
    get_asr_runtime,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
MEDIA_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".mp4", ".mov", ".mkv", ".webm"}


def _input(request: dict[str, Any]) -> Path | None:
    value = request.get("input")
    path = Path(str(value)).expanduser() if value else None
    return path if path and path.is_file() else None


def _ocr_with_tesseract(path: Path, language: str) -> dict[str, Any]:
    import pytesseract
    from PIL import Image

    with Image.open(path) as image:
        data = pytesseract.image_to_data(
            image,
            lang=language,
            output_type=pytesseract.Output.DICT,
        )
    words = []
    confidences = []
    for index, text in enumerate(data.get("text", [])):
        value = str(text or "").strip()
        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError, KeyError):
            confidence = -1
        if value:
            words.append(
                {
                    "text": value,
                    "confidence": confidence,
                    "bbox": [
                        int(data["left"][index]),
                        int(data["top"][index]),
                        int(data["width"][index]),
                        int(data["height"][index]),
                    ],
                    "block": int(data["block_num"][index]),
                    "paragraph": int(data["par_num"][index]),
                    "line": int(data["line_num"][index]),
                }
            )
            if confidence >= 0:
                confidences.append(confidence)
    ordered = sorted(words, key=lambda item: (item["block"], item["paragraph"], item["line"], item["bbox"][1], item["bbox"][0]))
    text = " ".join(item["text"] for item in ordered)
    return {
        "text": text,
        "regions": ordered,
        "confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "engine": "tesseract",
    }


def _write_ocr_outputs(request: dict[str, Any], source: Path, payload: dict[str, Any]):
    formats = request.get("formats") or ["json", "markdown", "txt"]
    if isinstance(formats, str):
        formats = [formats]
    artifacts = []
    for format_name in formats:
        normalized = str(format_name).lower()
        if normalized == "json":
            output = safe_output_path(request, source=source, stem_suffix="ocr", extension=".json")
            output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        elif normalized in {"markdown", "md"}:
            output = safe_output_path(request, source=source, stem_suffix="ocr", extension=".md")
            output.write_text(f"# OCR: {source.name}\n\n{payload['text']}\n", encoding="utf-8")
        elif normalized == "txt":
            output = safe_output_path(request, source=source, stem_suffix="ocr", extension=".txt")
            output.write_text(payload["text"] + "\n", encoding="utf-8")
        elif normalized == "csv":
            output = safe_output_path(request, source=source, stem_suffix="ocr", extension=".csv")
            with output.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["text", "confidence", "bbox", "block", "paragraph", "line"])
                writer.writeheader()
                for row in payload["regions"]:
                    writer.writerow({**row, "bbox": json.dumps(row["bbox"])})
        elif normalized == "xlsx":
            try:
                from openpyxl import Workbook
            except ImportError:
                continue
            output = safe_output_path(request, source=source, stem_suffix="ocr", extension=".xlsx")
            book = Workbook(); sheet = book.active; sheet.title = "OCR"
            sheet.append(["text", "confidence", "left", "top", "width", "height", "block", "paragraph", "line"])
            for row in payload["regions"]:
                sheet.append([row["text"], row["confidence"], *row["bbox"], row["block"], row["paragraph"], row["line"]])
            book.save(output)
        else:
            continue
        artifacts.append(
            artifact(
                output,
                operation="ocr",
                source=source,
                extra={"language": request.get("language", "chi_sim+eng"), "confidence": payload.get("confidence")},
            )
        )
    return artifacts


def _advanced_ocr(request: dict[str, Any]) -> dict[str, Any]:
    source = _input(request)
    if source is None:
        return invalid("input must reference an existing image or scanned document")
    if source.suffix.lower() == ".pdf":
        return result(
            SkillStatus.UNSUPPORTED,
            "PDF OCR is delegated to the QwenPaw built-in pdf Skill",
            error_code="USE_BUILTIN_PDF",
        )
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        return invalid("advanced-ocr accepts image inputs; use builtin pdf for PDF")
    resolver = CapabilityResolver()
    capabilities = resolver.resolve_many(("paddleocr", "tesseract", "openpyxl"))
    if (request.get("table") or request.get("layout")) and not capabilities["paddleocr"]["available"]:
        return result(
            SkillStatus.MODEL_RUNTIME_REQUIRED,
            "Complex table/layout recognition requires a configured PaddleOCR layout Runtime",
            error_code="MODEL_RUNTIME_REQUIRED",
            capabilities=capabilities,
        )
    language = str(request.get("language") or "chi_sim+eng")
    engine = str(request.get("engine") or "auto").lower()
    selected = None
    if engine in {"auto", "paddleocr"} and capabilities["paddleocr"]["available"]:
        selected = "paddleocr"
    elif engine in {"auto", "tesseract"} and capabilities["tesseract"]["available"]:
        selected = "tesseract"
    if selected is None:
        return result(
            SkillStatus.DEPENDENCY_MISSING,
            "No OCR engine is available; install PaddleOCR or Tesseract",
            error_code="OCR_ENGINE_MISSING",
            capabilities=capabilities,
        )
    if selected == "paddleocr":
        return result(
            SkillStatus.MODEL_RUNTIME_REQUIRED,
            "PaddleOCR is installed but a configured local model Runtime adapter is required",
            error_code="MODEL_RUNTIME_REQUIRED",
            capabilities=capabilities,
        )
    try:
        payload = _ocr_with_tesseract(source, language)
    except Exception as exc:
        return result(SkillStatus.FAILED, "OCR engine failed", error_code=type(exc).__name__, error_detail=str(exc), capabilities=capabilities)
    outputs = _write_ocr_outputs(request, source, payload)
    status = SkillStatus.SUCCESS
    message = "OCR completed"
    if not outputs:
        status = SkillStatus.PARTIAL_SUCCESS
        message = "OCR completed but no requested output format could be generated"
    return result(status, message, data=payload, artifacts=outputs, capabilities=capabilities)


def _ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,format_name:stream=codec_type,codec_name,channels,sample_rate,width,height",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe failed")
    return json.loads(completed.stdout)


def _transcript_report(transcript: str) -> str:
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    action_pattern = re.compile(r"(?:todo|action|行动项|待办|需要|负责)", re.I)
    decision_pattern = re.compile(r"(?:decision|决定|确认|结论|通过)", re.I)
    actions = [line for line in lines if action_pattern.search(line)]
    decisions = [line for line in lines if decision_pattern.search(line)]
    keywords = []
    counts: dict[str, int] = {}
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,6}", transcript):
        normalized = word.lower()
        counts[normalized] = counts.get(normalized, 0) + 1
    keywords = [item[0] for item in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:12]]
    summary = "\n".join(lines[:5]) or "No transcript content."
    return (
        "# Media Transcript Report\n\n"
        f"## Summary\n\n{summary}\n\n"
        "## Action Items\n\n" + ("\n".join(f"- {item}" for item in actions) or "- None detected") +
        "\n\n## Decisions\n\n" + ("\n".join(f"- {item}" for item in decisions) or "- None detected") +
        "\n\n## Keywords\n\n" + ", ".join(keywords) + "\n\n"
        "## Transcript\n\n" + transcript + "\n"
    )


def _subtitle_time(seconds: float, *, vtt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _write_transcript_outputs(request: dict[str, Any], transcript: str, segments: list[dict[str, Any]]):
    formats = request.get("formats") or ["markdown"]
    if isinstance(formats, str): formats = [formats]
    artifacts = []
    for name in formats:
        normalized = str(name).lower()
        if normalized in {"markdown", "md"}:
            output = safe_output_path(request, source=None, stem_suffix="transcript", extension=".md")
            output.write_text(_transcript_report(transcript), encoding="utf-8")
        elif normalized == "txt":
            output = safe_output_path(request, source=None, stem_suffix="transcript", extension=".txt")
            output.write_text(transcript + "\n", encoding="utf-8")
        elif normalized in {"srt", "vtt"}:
            output = safe_output_path(request, source=None, stem_suffix="transcript", extension=f".{normalized}")
            lines = ["WEBVTT", ""] if normalized == "vtt" else []
            for index, segment in enumerate(segments, 1):
                if normalized == "srt": lines.append(str(index))
                lines.append(f"{_subtitle_time(float(segment.get('start', 0)), vtt=normalized == 'vtt')} --> {_subtitle_time(float(segment.get('end', 0)), vtt=normalized == 'vtt')}")
                speaker = str(segment.get("speaker") or "").strip()
                lines += [(f"[{speaker}] " if speaker else "") + str(segment.get("text") or ""), ""]
            output.write_text("\n".join(lines), encoding="utf-8")
        else:
            continue
        duration = max((float(item.get("end", 0)) for item in segments), default=0)
        artifacts.append(artifact(output, operation="media-transcriber", extra={"duration": duration, "format": normalized}))
    return artifacts


def _media_transcriber(request: dict[str, Any]) -> dict[str, Any]:
    source = _input(request)
    operation = str(request.get("operation") or "transcribe")
    resolver = CapabilityResolver()
    capabilities = resolver.resolve_many(("ffmpeg", "asr"))
    if operation in {"summarize_transcript", "export_transcript"}:
        transcript = str(request.get("transcript") or "").strip()
        if not transcript:
            return invalid("summarize_transcript requires transcript text")
        segments = request.get("segments") or [{"start": 0, "end": 0, "text": transcript}]
        if not isinstance(segments, list): return invalid("segments must be a list")
        artifacts = _write_transcript_outputs(request, transcript, segments)
        return result(SkillStatus.SUCCESS, "Transcript outputs generated", data={"segments": len(segments), "speaker_diarization": any(item.get("speaker") for item in segments if isinstance(item, dict))}, artifacts=artifacts, capabilities=capabilities)
    if source is None or source.suffix.lower() not in MEDIA_SUFFIXES:
        return invalid("input must reference a supported audio or video file")
    if not capabilities["ffmpeg"]["available"]:
        return result(SkillStatus.DEPENDENCY_MISSING, "ffmpeg/ffprobe is required", error_code="FFMPEG_MISSING", capabilities=capabilities)
    try:
        metadata = _ffprobe(source)
    except Exception as exc:
        return result(SkillStatus.FAILED, "Media inspection failed", error_code=type(exc).__name__, error_detail=str(exc), capabilities=capabilities)
    duration = float(metadata.get("format", {}).get("duration") or 0)
    media_format = str(metadata.get("format", {}).get("format_name") or source.suffix.lstrip("."))
    if operation == "inspect":
        return result(SkillStatus.SUCCESS, "Media inspection completed", data={"duration": duration, "format": media_format, "streams": metadata.get("streams", [])}, capabilities=capabilities)
    if operation == "extract_audio":
        output = safe_output_path(request, source=source, stem_suffix="audio", extension=".wav")
        completed = subprocess.run(["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(output)], capture_output=True, text=True, timeout=300, check=False)
        if completed.returncode != 0 or not output.is_file():
            return result(SkillStatus.FAILED, "Audio extraction failed", error_code="FFMPEG_FAILED", error_detail=completed.stderr[-1000:], capabilities=capabilities)
        item = artifact(output, operation=operation, source=source, extra={"duration": duration, "format": "wav"})
        return result(SkillStatus.SUCCESS, "Audio extraction completed", artifacts=[item], capabilities=capabilities)
    if not capabilities["asr"]["available"]:
        return result(
            SkillStatus.MODEL_RUNTIME_REQUIRED,
            "Transcription requires faster-whisper and an accessible local model",
            data={"duration": duration, "format": media_format},
            error_code="MODEL_RUNTIME_REQUIRED",
            capabilities=capabilities,
        )
    try:
        payload = dict(
            get_asr_runtime(request).transcribe(
                source,
                language=str(request.get("language") or "").strip() or None,
                diarization=bool(request.get("diarization")),
            )
        )
    except RuntimeUnavailableError as exc:
        return result(
            SkillStatus.MODEL_RUNTIME_REQUIRED,
            "The faster-whisper Runtime or configured model is unavailable",
            data={"duration": duration, "format": media_format},
            error_code="MODEL_RUNTIME_REQUIRED",
            error_detail=str(exc),
            capabilities=capabilities,
        )
    except RuntimeExecutionError as exc:
        return result(
            SkillStatus.RUNTIME_ERROR,
            "The faster-whisper Runtime failed",
            data={"duration": duration, "format": media_format},
            error_code="RUNTIME_ERROR",
            error_detail=str(exc),
            capabilities=capabilities,
        )
    segments = payload.get("segments")
    transcript = str(payload.get("text") or "").strip()
    if not isinstance(segments, list):
        return result(
            SkillStatus.RUNTIME_ERROR,
            "The faster-whisper Runtime returned invalid segments",
            error_code="RUNTIME_ERROR",
            capabilities=capabilities,
        )
    outputs = _write_transcript_outputs(request, transcript, segments)
    payload.setdefault("duration", duration)
    payload["media_format"] = media_format
    return result(
        SkillStatus.SUCCESS,
        "Media transcription completed",
        data=payload,
        artifacts=outputs,
        capabilities=capabilities,
    )


def execute(skill_name: str, request: dict[str, Any]) -> dict[str, Any]:
    if skill_name == "advanced-ocr":
        if str(request.get("operation") or "").lower() == "batch":
            inputs = request.get("inputs")
            if not isinstance(inputs, list) or not inputs: return invalid("batch OCR requires inputs")
            responses = []; artifacts = []
            for value in inputs:
                child = dict(request); child["input"] = value; child["operation"] = "ocr"; child.pop("inputs", None)
                response = _advanced_ocr(child); responses.append({"input": Path(str(value)).name, "status": response["status"]}); artifacts.extend(response.get("artifacts", []))
            failures = [item for item in responses if item["status"] != "SUCCESS"]
            return result(SkillStatus.PARTIAL_SUCCESS if failures else SkillStatus.SUCCESS, "Batch OCR completed" if not failures else "Batch OCR requires missing dependencies for some inputs", data={"items": responses}, artifacts=artifacts, error_code="BATCH_ITEM_FAILED" if failures else None)
        return _advanced_ocr(request)
    if skill_name == "media-transcriber":
        return _media_transcriber(request)
    return invalid(f"Unsupported OCR/media Skill: {skill_name}")
