# Font resources

No font binary is bundled with PDF Editor.

Resolution order for page numbers and other required Chinese glyphs:

1. a complete render-capable font already embedded in the source PDF;
2. a legally supplied font in this directory or `font-registry/`;
3. a system CJK font such as Noto Sans SC, Microsoft YaHei, DengXian, SimHei, or SimSun;
4. PyMuPDF's registered `china-s` font, only after glyph coverage and isolated rendering succeed.

Additional private directories can be supplied with `PDF_EDITOR_FONT_DIRS`. If no candidate renders every required glyph, execution fails with `FONT_GLYPH_UNAVAILABLE` and no successful output is returned.
