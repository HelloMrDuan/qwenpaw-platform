---
name: advanced-ocr
description: "Image OCR orchestration with text, confidence, bounding boxes and structured output; PDF OCR stays built-in."
---

# advanced-ocr

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Operations

- `ocr`
- `batch`
- `layout`
- `table`
- `json`
- `markdown`
- `txt`
- `csv`
- `xlsx`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"ocr"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: paddleocr.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
