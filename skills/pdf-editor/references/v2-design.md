# V2 text replacement design

The core contract is **content correctness + visual placement correctness**.

For equal-length text:
1. Extract raw character data (`rawdict`).
2. Locate each source character's bbox and origin.
3. Resolve a render-capable font.
4. Redact only the source character boxes.
5. Insert each replacement character at the corresponding original origin.
6. Preserve original font size, color and baseline.
7. Fit each glyph to the original character advance with bounded horizontal scaling.
8. Pixel-check each inserted glyph immediately.
9. Save transactionally, reopen, and semantic-check the final PDF.

Font resolution order:
1. exact embedded font, but only after isolated glyph rendering succeeds;
2. exact full font in private registry/system;
3. controlled visual CJK family match in `auto` mode;
4. fail if no render-capable font exists.
