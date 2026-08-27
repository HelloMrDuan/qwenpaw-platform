---
name: image-toolkit
description: "Process at least one existing input image with deterministic Pillow inspection, conversion, geometry, metadata, batch, or duplicate operations. Never use for text-to-image or generating a new image from a prompt."
---

# image-toolkit

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Routing boundary

This Skill requires at least one existing input image supplied or referenced by
the user. Do not select it for text-to-image requests or requests to generate,
draw, or create a new image from a text prompt.

## Operations

- `info`
- `exif`
- `hash`
- `convert`
- `resize`
- `fit` (`cover`, `contain`, or explicit `stretch`)
- `crop`
- `rotate`
- `flip`
- `compress`
- `quality`
- `dpi`
- `strip_exif`
- `alpha`
- `concat`
- `split`
- `to_pdf`
- `duplicates`
- `batch_convert`
- `batch_compress`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"info"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: none.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
