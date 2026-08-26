---
name: photo-restoration
description: "Traditional old-photo restoration pipeline with explicit optional AI restoration Runtime stages."
---

# photo-restoration

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Operations

- `inspect`
- `pipeline`
- `comparison`
- `batch`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"inspect"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: realesrgan, gfpgan, codeformer, lama, colorization.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
