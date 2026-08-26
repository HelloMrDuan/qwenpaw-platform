---
name: api-debugger
description: "Offline HTTP evidence diagnosis and reproducible curl/Python/Java request generation."
---

# api-debugger

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Operations

- `analyze`
- `generate_curl`
- `generate_python`
- `generate_java`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"analyze"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: none.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
