# PDF Editor Production V1 plan schema

## replace_text

```json
{
  "action": "replace_text",
  "pages": "all",
  "old": "乌审旗",
  "new": "杭锦旗",
  "font_policy": "auto",
  "occurrence": "all",
  "required": true,
  "background": [1, 1, 1]
}
```

`occurrence`: `"all"`, integer, integer list, or range string.

## delete_text

```json
{"action":"delete_text","pages":[1],"text":"作废","occurrence":"all"}
```

## delete_pages

```json
{"action":"delete_pages","pages":[3]}
```

## insert_pages - blank

```json
{"action":"insert_pages","at":2,"count":1,"copy_size_from":1}
```

## insert_pages - from another PDF

```json
{"action":"insert_pages","at":2,"source":"/abs/other.pdf","source_pages":"1,3"}
```

## reorder_pages

The list must be a full permutation of all current pages.

```json
{"action":"reorder_pages","order":[3,1,2]}
```

## rotate_pages

```json
{"action":"rotate_pages","pages":[2],"degrees":90}
```

## add_text

```json
{"action":"add_text","pages":[1],"text":"内部资料","position":"top-right","font_size":12}
```

## watermark

```json
{"action":"watermark","pages":"all","text":"内部资料","font_size":42,"opacity":0.15}
```

## page_numbers

```json
{"action":"page_numbers","pages":"all","format":"第 {page} 页 / 共 {total} 页","font_size":9}
```

V1.2 requires a complete CJK font and post-save visual glyph validation. Missing glyph coverage fails with `FONT_GLYPH_UNAVAILABLE`.

## add_image

```json
{"action":"add_image","pages":[1],"path":"/abs/logo.png","rect":[420,60,540,105]}
```

or use `position`, `width`, optional `height`.

## replace_image

```json
{"action":"replace_image","page":1,"image_index":1,"path":"/abs/new-logo.png"}
```

or specify `xref` directly. Replacement is shared-xref based. If the xref is referenced on multiple pages, a page-subset request is rejected as unsafe. V1.2 records `before_image_geometry`, `after_image_geometry`, and `geometry_diff`, and rejects placement changes, overlays, unchanged target content, or excessive non-target visual differences.
