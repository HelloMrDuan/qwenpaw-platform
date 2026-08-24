# Changelog

## 1.2.0 - 2026-08-24

### Added

- Standard `skill.yaml`, `SkillRequest`/`SkillResult` executor adapter, JSON schemas and Contract tests.
- Standard `tool.start`, `tool.progress`, `file.created`, `tool.result` and `tool.error` mapping.
- Five-layer PASS contract: execution, reopen, semantic, visual and geometry/layout validation.
- Real page-tree, order, xref and independent-render validation for `insert_pages`.
- Before/after image geometry, target/non-target visual and no-overlay validation for `replace_image`.
- Complete CJK font resolution, coverage checks and post-render glyph validation for page numbers.

### Changed

- Engine imports the supported `pymupdf` module directly so CLI stdout remains valid JSON with PyMuPDF 1.28.
- Progress event names now use `file.created` and `tool.error` from the platform contract.
- `SkillResult` serialization includes derived `status` and structured `validation`.

### Preserved

- Existing `SKILL.md` discovery and `scripts/pdf_editor.py` CLI entrypoint.
- V2 character-level `replace_text` matching, redaction and glyph placement algorithm.

### Fixed

- False-positive blank-page insertion acceptance.
- Image replacement acceptance without geometry and visual proof.
- Chinese page-number corruption caused by hard-coded Helvetica.
