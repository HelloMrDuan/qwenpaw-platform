# Core Productivity Skill Pack

> Phase: 15.0
> Scope: 17 incremental custom Skills plus the retained Advanced PDF Editor
> Official de-duplication baseline: QwenPaw `v2.1.0`, commit
> `e4995dcf516d27400fbc33891aa3dcbcf79acc7a`

## 1. De-duplication decision

The official v2.1.0 source contains mature built-in Skills for `pdf`, `docx`,
`xlsx`, `pptx`, `browser`, `cron`, `file_reader`, `make_plan`,
`multi_agent_collaboration`, `channel_message`, agent chat and email integration.
This pack does not recreate them.

- ordinary PDF read/OCR/merge/split/rotation/encryption stays built-in;
- Office document editing stays in built-in `docx`, `xlsx` and `pptx`;
- web access stays in the built-in Browser; `web-research-report` only defines
  evidence methodology and synthesis;
- document batch processing inventories, classifies and delegates format-specific
  operations to built-ins;
- Channel messaging, planning and multi-agent orchestration are outside this pack.

## 2. Included custom Skills

### Image, OCR and media

1. `image-toolkit`
2. `photo-restoration`
3. `advanced-ocr`
4. `media-transcriber`
5. `image-background-tools`
6. `image-quality-enhancer`

### Development and operations diagnostics

7. `sql-diagnostics`
8. `log-incident-analyzer`
9. `api-debugger`
10. `ops-troubleshooter`
11. `network-diagnostics`
12. `config-diagnostics`

### Data, file and engineering productivity

13. `archive-inspector`
14. `data-profiler`
15. `document-batch-processor`
16. `release-notes`
17. `web-research-report`

The existing `pdf-editor` v1.2 is retained and released as
`advanced-pdf-editor.skill.zip`. Its engine is unchanged.

## 3. Execution architecture

```text
SKILL.md
  -> scripts/run.py
  -> structured JSON request
  -> CapabilityResolver
  -> native handler / optional Runtime / safe fallback
  -> structured SkillResult
  -> Artifact metadata + immutable output
```

The repository has one canonical execution core under
`core/productivity_skills/`. `scripts/build_skill_pack.py` copies only the
required internal runtime and handler group into each ZIP. An installed ZIP
therefore runs without the repository, while development avoids maintaining 17
independent copies of the same dependency logic.

## 4. Result and Artifact contract

Every response uses one of:

- `SUCCESS`
- `PARTIAL_SUCCESS`
- `DEPENDENCY_MISSING`
- `MODEL_RUNTIME_REQUIRED`
- `UNSUPPORTED`
- `INVALID_INPUT`
- `FAILED`

A file-producing result includes an Artifact with `operation`, `source`,
`output`, `mime_type`, `size` and SHA256 `checksum`. Image Artifacts add width
and height; OCR adds language and confidence; media adds duration and format;
data reports add rows and columns. Source files are never overwritten.

## 5. Safety guarantees

- SQL, API, operations and network diagnostics are analysis/dry-run by default;
- configuration reports redact sensitive values;
- archive extraction blocks absolute paths, `..`, drive paths, links and Zip
  Slip candidates;
- model weights are never bundled or downloaded automatically;
- unavailable OCR/ASR/restoration/segmentation never reports success;
- no release contains `.env`, database state, logs, caches, Secrets, weights or
  local machine paths;
- Office/PDF format mutation is delegated to the corresponding built-in Skill.

## 6. Hermes boundary

Hermes is `ARCHIVED / REFERENCE ONLY`. The retained source may inform
multi-agent lifecycle, tool concurrency, Skill orchestration, memory/context and
session design. It is not a production Runtime, Gateway or dependency of this
Skill Pack.
