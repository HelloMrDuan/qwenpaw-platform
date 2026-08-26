# Skill Runtime Capabilities

## 1. CapabilityResolver

`core/productivity_skills/capabilities.py` is the single detection point. A
Skill asks it for a named capability and receives:

```json
{
  "name": "realesrgan",
  "available": false,
  "mode": "runtime_required"
}
```

Modes are `native`, `runtime`, `dependency_missing`, `runtime_required` and
`unsupported`. Handlers do not infer availability from a filename, prompt or
requested operation.

## 2. Current local environment audit

| Capability | Class | Current state | Used by |
| --- | --- | --- | --- |
| Pillow | `REQUIRED` for image Skills | AVAILABLE | Image toolkit/restoration/background/quality |
| OpenCV | `OPTIONAL` | NOT INSTALLED | scratch/defect and advanced native image paths |
| ImageMagick | `OPTIONAL` | NOT INSTALLED | optional conversions |
| ffmpeg/ffprobe | `OPTIONAL` | AVAILABLE | media inspection/extraction |
| Tesseract binary | `OPTIONAL` | NOT INSTALLED | OCR fallback (`pytesseract` wrapper alone is insufficient) |
| PaddleOCR | `RUNTIME` | NOT INSTALLED in project venv | Chinese/mixed OCR and layout/table adapter |
| openpyxl | `OPTIONAL` | AVAILABLE | OCR XLSX output, XLSX profiling/report |
| PyArrow | `OPTIONAL` | NOT INSTALLED | Parquet profiling |
| PyYAML | `OPTIONAL` | NOT INSTALLED | YAML/Compose/Kubernetes config parsing |
| 7z | `OPTIONAL` | NOT INSTALLED | 7z archive support |
| Whisper/FunASR | `RUNTIME` | NOT INSTALLED | ASR |
| Real-ESRGAN | `RUNTIME` | NOT INSTALLED | AI super-resolution |
| GFPGAN | `RUNTIME` | NOT INSTALLED | face restoration |
| CodeFormer | `RUNTIME` | NOT INSTALLED | face restoration |
| LaMa | `RUNTIME` | NOT INSTALLED | defect/scratch inpainting |
| Colorization Runtime | `RUNTIME` | NOT INSTALLED | black-and-white colorization |
| rembg/segmentation | `RUNTIME` | NOT INSTALLED | complex background removal/matting |

The audit is specific to the project venv and system commands observed during
Phase 15. Deployment must re-run capability discovery.

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
4. Never download weights implicitly.
5. Never turn resize/sharpen/contrast into a claim of AI restoration.
