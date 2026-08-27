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
| rembg + u2netp | `INSTALLED` | `WIRED` | `READY` when u2netp exists in workspace cache | segment and alpha-matting path |
| PaddleOCR | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| Real-ESRGAN | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| GFPGAN | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| CodeFormer | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |
| LaMa | `MISSING / BLOCKED` | Not wired | `MODEL_RUNTIME_REQUIRED` | Deferred |

## Evidence boundary

Installation states above come from the supplied Phase 17.0 real QwenPaw cloud
validation. Phase 17.1 repository tests validate Adapter contracts, normalized
outputs, subtitle/Artifact generation, Alpha PNG output, package isolation and
failure degradation without downloading model weights locally. The rebuilt ZIPs
must be redeployed to exercise the newly wired adapters in that cloud tenant.
