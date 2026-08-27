# Runtime Capability Status

## Status contract

`CapabilityResolver` now reports `AVAILABLE`, `DEGRADED`, `MISSING`, or
`RUNTIME_ERROR` while preserving the compatible `available` and `mode` fields.

| Status | Meaning |
| --- | --- |
| `AVAILABLE` | Package/binary, adapter and configured model are accessible |
| `DEGRADED` | Package and adapter exist, but a configured local model is unavailable |
| `MISSING` | Required binary or Python package is absent |
| `RUNTIME_ERROR` | Adapter health load or minimum inference failed |

## Phase 17.1 matrix

| Capability | Real cloud installation | Adapter | Skill state after wiring | Notes |
| --- | --- | --- | --- | --- |
| OpenCV | `AVAILABLE` | Native | `READY` | No Phase 17.1 code change |
| ffmpeg / ffprobe | `AVAILABLE` | Native | `READY` | media probe/extract already wired |
| Tesseract 5.3.0 + `chi_sim` + `eng` | `AVAILABLE` | Existing | `READY` | advanced OCR passed real cloud validation |
| faster-whisper | `INSTALLED` | `WIRED` | `READY` when local model/cache configuration is present | TXT/Markdown/SRT/VTT normalized output |
| rembg + u2netp | `INSTALLED` | `WIRED` | `READY` when u2netp is discovered in a supported local cache | segment and alpha-matting path |
| PaddleOCR | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| Real-ESRGAN | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| GFPGAN | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| CodeFormer | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| LaMa | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |

## Evidence boundary

Installation states above come from Phase 17.0 real QwenPaw cloud validation.
Phase 17.2 subsequently validated the wired packages in that tenant:

- `media-transcriber`: faster-whisper Chinese transcription and all four export
  formats passed;
- `image-background-tools`: rembg segment, alpha matting and RGBA Alpha PNG
  passed;
- strict Runtime state: `asr=AVAILABLE`, `background_removal=AVAILABLE`.

Phase 17.3 removes the temporary-environment dependency by discovering existing
HF and rembg caches offline. The newly rebuilt persistence-hardened ZIPs still
require deployment verification, but they do not require a new model download.
