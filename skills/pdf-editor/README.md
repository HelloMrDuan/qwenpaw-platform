# PDF Editor V1.2

PDF Editor is the first standardized QwenPaw workspace Skill. It retains the existing QwenPaw discovery path and deterministic engine while adding an optional Extension Contract adapter.

## Compatibility paths

- QwenPaw discovery: `SKILL.md`
- Existing CLI engine: `scripts/pdf_editor.py`
- Standard Contract adapter: `executor/main.py` → `execute()`
- Request/Result schemas: `schemas/`

The executor never contains PDF mutation algorithms. It resolves controlled Artifacts, writes an edit plan, invokes the existing engine, validates the result, publishes the output Artifact, and returns `SkillResult` with `StreamEvent` objects.

## V1.2 PASS contract

Success requires all of the following:

1. operation execution passes;
2. the saved PDF reopens;
3. semantic validation passes;
4. visual rendering validation passes;
5. geometry/layout validation passes where applicable.

An engine process returning `ok=true` is not sufficient by itself.

## P0 operation guarantees

- `insert_pages`: verifies page-tree growth, new page xrefs, independent rendering, source-page order movement, and the reopened final snapshot.
- `replace_image`: records before/after xref, bbox, transform, width, height and rotation; validates placement tolerance, new visual content, old-content removal, non-target stability and no overlay.
- `page_numbers`: resolves a complete CJK font, validates glyph coverage before drawing, and verifies real rendered glyphs for `第`, `页`, and `共` after reopening.

## Local engine usage

```powershell
.venv\Scripts\python.exe skills\pdf-editor\scripts\pdf_editor.py info --input input.pdf
.venv\Scripts\python.exe skills\pdf-editor\scripts\pdf_editor.py apply --input input.pdf --output output.pdf --plan plan.json
```

## Local Contract test

```powershell
.venv\Scripts\python.exe -m unittest discover -s skills\pdf-editor\tests -p "test_*.py" -v
```

Tests use generated fixtures unless a separately controlled real-document suite is supplied. Generated fixture success must be reported as `AUTOMATED FIXTURE PASS`, never as real-document acceptance.
