---
name: image-quality-enhancer
description: "Enhance or upscale at least one existing input image using traditional processing and optional AI super-resolution. Never use for text-to-image or generating a new image from a prompt."
---

# image-quality-enhancer

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Routing boundary

This Skill requires at least one existing input image supplied or referenced by
the user. Do not select it for text-to-image requests or requests to generate,
draw, or create a new image from a text prompt.

## Operations

- `enhance`
- `upscale_2x`
- `upscale_4x`
- `denoise`
- `sharpen`
- `gamma`
- `white_balance`
- `batch`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"enhance"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: realesrgan.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
