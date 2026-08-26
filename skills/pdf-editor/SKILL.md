---
name: pdf-editor
description: "Advanced deterministic PDF editing for precise image/text placement, bbox/transform/layout preservation, validated page insertion, Chinese page numbering and visual QA. Use QwenPaw builtin pdf for ordinary reading, OCR, merge, split, rotation and encryption."
---

# Advanced PDF Editor - Production V1.2

## Routing boundary

Use the QwenPaw built-in `pdf` Skill for ordinary PDF reading, OCR, merge,
split, rotation and encryption. Use this Advanced PDF Editor only when the task
needs precise image replacement, bounding-box/transform preservation, validated
page insertion, Chinese page numbering, precise text insertion, layout
preservation or visual validation.

Use this skill when the user wants to **modify a PDF and receive a new PDF**.

## Mandatory rules

1. Never overwrite the source PDF. Default output: `<original>_edited.pdf`.
2. Use the exact mounted attachment path supplied by the runtime. Never invent attachment paths.
3. All PDF modifications MUST use `scripts/pdf_editor.py`. Do not write ad-hoc PyMuPDF / fitz / ReportLab fallbacks after an error.
4. Preserve the V2 text replacement engine. Do not replace it with line redraw logic.
5. For text replacement, default `font_policy` is `auto`; use `exact` only when the user explicitly requires exact font family preservation.
6. Only claim success when `operation_execution_ok`, `reopen_ok`, `semantic_ok`, `visual_ok`, and applicable `geometry_layout_ok` are all true.
7. If visual validation fails, do not return the generated PDF as a successful result.
8. Never silently switch fonts and call it exact preservation. Report `font_kind` / `font_source` when relevant.
9. Keep destructive actions transactional and on a new output file.
10. If the PDF is image-only/scanned, report that OCR editing is required; do not pretend native text editing succeeded.

## Recommended workflow

### 1. Inspect and classify

```bash
python scripts/pdf_editor.py info --input "/absolute/path/input.pdf"
```

Check `classification.primary_type`, `has_subset_fonts`, `has_forms`, and page-level types.

### 2. Create a JSON plan

Example:

```json
{
  "operations": [
    {
      "action": "replace_text",
      "pages": "all",
      "old": "乌审旗",
      "new": "杭锦旗",
      "font_policy": "auto"
    }
  ]
}
```

### 3. Apply

For normal execution:

```bash
python scripts/pdf_editor.py apply \
  --input "/absolute/path/input.pdf" \
  --output "/absolute/path/input_edited.pdf" \
  --plan "/absolute/path/edit_plan.json"
```

For progress-aware execution:

```bash
PDF_EDITOR_PROGRESS=1 python scripts/pdf_editor.py apply \
  --input "/absolute/path/input.pdf" \
  --output "/absolute/path/input_edited.pdf" \
  --plan "/absolute/path/edit_plan.json"
```

Progress JSONL is written to stderr so the final stdout JSON remains intact.

Standard event names are `tool.start`, `tool.progress`, `file.created`, `tool.result`, and `tool.error`.

### 4. Return only validated outputs

Return the new PDF, never the original.

## Supported plan operations

- `replace_text`
- `delete_text`
- `delete_pages`
- `insert_pages`
- `reorder_pages`
- `rotate_pages`
- `add_text`
- `watermark`
- `page_numbers`
- `add_image`
- `replace_image`

Separate deterministic commands:

- `merge`
- `extract`
- `split`

Page numbers are 1-based.

`insert_pages`, `replace_image`, and `page_numbers` have mandatory operation-specific structural, geometry, and glyph validation in V1.2. A successful process exit is not sufficient.

## Standard Extension Contract

The existing QwenPaw discovery and CLI paths remain unchanged. For platform Extension Contract callers, use:

```text
executor.main:execute
```

The adapter accepts `core.contracts.SkillRequest`, resolves controlled input Artifacts, invokes `scripts/pdf_editor.py`, and returns `core.contracts.SkillResult` with validated output Artifacts and StreamEvents. It never duplicates PDF mutation logic.

## Text replacement behavior

For equal-length replacements, the engine:

- reads raw character bbox/origin data;
- resolves a render-capable font;
- redacts only the exact source character boxes;
- inserts each new character at the original character origin;
- keeps baseline, font size, color and character spacing;
- pixel-validates every inserted glyph immediately;
- reopens the saved PDF and validates scoped text counts;
- compares source/output renders outside the edited region and rejects excessive non-target change.

`occurrence` can be `"all"`, a 1-based integer, a list, or a range string such as `"1,3-4"`.

## Font registry

Private exact fonts may be supplied in:

```text
font-registry
```

or `resources/fonts/` in a private deployment. System CJK fonts are discovered on supported hosts.

or via:

```text
PDF_EDITOR_FONT_DIRS=font-registry
```

Do not bundle or expose proprietary font files in this Skill.

## Current scan/OCR boundary

`info` detects `scanned_candidate` pages. Production V1 does not OCR-repaint image-only PDFs. That is a separate OCR editing module and must not be simulated by native text replacement.
