# Skill Runtime Capabilities

## 1. CapabilityResolver

`core/productivity_skills/capabilities.py` is the single detection point. A
Skill asks it for a named capability and receives:

```json
{
  "name": "asr",
  "available": true,
  "status": "AVAILABLE",
  "mode": "runtime",
  "version": "installed package version",
  "python_package": "faster-whisper",
  "runtime_test": "model_accessible",
  "error": null
}
```

Statuses are `AVAILABLE`, `DEGRADED`, `MISSING` and `RUNTIME_ERROR`. Compatible
modes remain `native`, `runtime`, `dependency_missing`, `runtime_required` and
`unsupported`. For model capabilities, import success alone is insufficient:
the adapter and configured model must also be accessible.

## 2. Real QwenPaw Runtime audit and Phase 17.1 wiring

| Capability | Class | Current state | Used by |
| --- | --- | --- | --- |
| Pillow | `REQUIRED` for image Skills | AVAILABLE | Image toolkit/restoration/background/quality |
| OpenCV | `OPTIONAL` | AVAILABLE in real cloud | traditional image paths |
| ffmpeg/ffprobe | `OPTIONAL` | AVAILABLE in real cloud | media inspection/extraction |
| Tesseract 5.3.0 + `chi_sim` + `eng` | `OPTIONAL` | AVAILABLE in real cloud | OCR text/bbox/confidence |
| PaddleOCR | `RUNTIME` | MISSING / BLOCKED | layout/table adapter remains deferred |
| openpyxl | `OPTIONAL` | AVAILABLE in real cloud | OCR XLSX output, XLSX profiling/report |
| faster-whisper | `RUNTIME` | INSTALLED + ADAPTER WIRED | ASR and subtitles |
| rembg + u2netp | `RUNTIME` | INSTALLED + ADAPTER WIRED | segment and alpha matting |
| Real-ESRGAN | `RUNTIME` | MISSING / BLOCKED | AI super-resolution |
| GFPGAN | `RUNTIME` | MISSING / BLOCKED | face restoration |
| CodeFormer | `RUNTIME` | MISSING / BLOCKED | optional face restoration |
| LaMa | `RUNTIME` | MISSING / BLOCKED | defect/scratch inpainting |

The installation evidence is from Phase 17.0 real cloud validation. Deployment
must run `scripts/check_runtime_capabilities.py --runtime-test` after placing
models in the workspace cache.

## 3. Dependency policy

- `REQUIRED`: small dependency essential to the Skill's native core (Pillow for
  image transformations).
- `OPTIONAL`: enables a format or enhanced deterministic path; absence returns
  `DEPENDENCY_MISSING` or leaves a documented fallback.
- `RUNTIME`: model-backed service or library with externally managed weights;
  absence returns `MODEL_RUNTIME_REQUIRED`.

No Skill ZIP contains wheels, shared libraries or model weights. Deployment
installs shared Python/CLI dependencies once for the workspace instead of
vendoring them into every Skill.

## 4. Fallback rules

1. Use deterministic native logic when it satisfies the named operation.
2. If an optional deterministic dependency is absent, return
   `DEPENDENCY_MISSING` unless a clearly labeled fallback actually ran.
3. If a traditional stage completed but requested AI stages did not, return
   `PARTIAL_SUCCESS` with `MODEL_RUNTIME_REQUIRED` details and the valid native
   Artifact.
4. Never download weights implicitly; an operator must opt in with
   `QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD=1`.
5. Never turn resize/sharpen/contrast into a claim of AI restoration.
