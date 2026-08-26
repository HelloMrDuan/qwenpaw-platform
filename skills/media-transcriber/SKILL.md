---
name: media-transcriber
description: "Media inspection/audio extraction plus ASR transcript and meeting-report orchestration."
---

# media-transcriber

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Operations

- `inspect`
- `extract_audio`
- `transcribe`
- `summarize_transcript`
- `export_transcript`

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{"operation":"inspect"}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: asr.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
