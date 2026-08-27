# Runtime Enhancement Pack

## Scope

Phase 17 adds shared, workspace-managed dependencies to the existing Core Skill
Pack. It does not add Skills, vendor model weights into release ZIPs, or modify
QwenPaw Runtime. Phase 17.1 wires only the two model Runtimes already verified
in the real cloud environment: `faster-whisper` and `rembg` with `u2netp`.

Phase 17.2 real cloud acceptance subsequently passed for both wired adapters:
Chinese faster-whisper transcription produced TXT, Markdown, SRT and VTT, and
rembg passed segment, alpha matting and RGBA Alpha PNG validation. Phase 17.3
hardens restart persistence so those results no longer depend on temporary
shell exports or enabling downloads.

## Real QwenPaw Runtime baseline

The Phase 17.0 cloud acceptance supplied for this repository records:

| Capability | Cloud state | Evidence |
| --- | --- | --- |
| OpenCV | `AVAILABLE` | Traditional image paths available |
| openpyxl | `AVAILABLE` | Workbook output available |
| ffmpeg / ffprobe | `AVAILABLE` | Probe and audio extraction ready |
| Tesseract 5.3.0 | `AVAILABLE` | `chi_sim`, `eng`, bbox and confidence passed |
| faster-whisper | `AVAILABLE` | Independent Runtime execution passed |
| rembg + u2netp | `AVAILABLE` | Independent background removal passed |
| PaddleOCR | `MISSING / BLOCKED` | Not handled in Phase 17.1 |
| Real-ESRGAN / GFPGAN / CodeFormer / LaMa | `MISSING / BLOCKED` | Not handled in Phase 17.1 |

## Adapter integration

### Faster Whisper

`FasterWhisperAdapter` lazily imports `faster_whisper.WhisperModel`, loads only
the configured local model, normalizes language/text/segments/timestamps and
optional probability signals, then delegates TXT, Markdown, SRT and VTT output
to the existing media export pipeline.

Supported model selectors are `tiny`, `base` and `small`. A local model path
takes precedence. Larger models are not selected by default.

### rembg

`RembgAdapter` lazily creates a rembg session and returns a validated PNG with
an alpha channel. Supported models are `u2netp`, `u2net` and
`isnet-general-use`; the default is the cloud-validated `u2netp`.
`bria-rmbg-2.0` is never selected implicitly and is rejected by this adapter.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `QWENPAW_WORKSPACE` | Workspace root used to resolve `.runtime` | Current working directory |
| `QWENPAW_RUNTIME_ROOT` | Shared Runtime state root | `<workspace>/.runtime` |
| `QWENPAW_ASR_MODEL_PATH` | Explicit local faster-whisper model directory | unset |
| `QWENPAW_ASR_MODEL` | Model name (`tiny`, `base`, `small`) | `tiny` |
| `QWENPAW_ASR_CACHE_DIR` | Additional ASR cache discovery root/download target | unset |
| `QWENPAW_ASR_DEVICE` | faster-whisper device | `auto` |
| `QWENPAW_ASR_COMPUTE_TYPE` | CTranslate2 compute type | `int8` |
| `QWENPAW_REMBG_MODEL` | rembg model | `u2netp` |
| `QWENPAW_REMBG_MODEL_DIR` | Additional rembg models root | unset |
| `QWENPAW_RUNTIME_ALLOW_MODEL_DOWNLOAD` | Explicit opt-in for model downloads | disabled |

Existing cloud models are discovered read-only from workspace caches,
HuggingFace standard caches and the standard rembg home cache. They do not need
to be copied or downloaded again. The optional normalization tool can create
directory symlinks into the workspace layout. Model directories are ignored by
Git and excluded by the Skill package builder.

## Failure semantics

- Missing package or inaccessible model: `MODEL_RUNTIME_REQUIRED`.
- Model load or inference failure: `RUNTIME_ERROR` with a structured error.
- Successful inference: `SUCCESS` plus normalized data and Artifact metadata.
- No adapter claims success after import-only discovery.

## Health probe

Run strict checks, including ASR model load and a minimum rembg inference:

```bash
python scripts/check_runtime_capabilities.py
```

Run path/package inspection without loading models:

```bash
python scripts/check_runtime_capabilities.py --inspect-only
```

Strict checks reuse a process-level Adapter instance after successful load and
never put model weights into a Skill ZIP.
