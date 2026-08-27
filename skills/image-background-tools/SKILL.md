---
name: image-background-tools
description: "Remove, replace, blur, or crop the background of at least one existing input image, with optional segmentation Runtime. Never use for text-to-image or generating a new image from a prompt."
---

# image-background-tools

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Routing boundary

This Skill requires at least one existing input image supplied or referenced by
the user. Do not select it for text-to-image requests or requests to generate,
draw, or create a new image from a text prompt.

## Operations

- `remove_solid`
- `transparent`
- `white`
- `black`
- `color`
- `replace`
- `blur`
- `crop_subject`
- `segment`
- `alpha_matting`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"remove_solid"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `RUNTIME_ERROR`/`FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: background_removal.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
