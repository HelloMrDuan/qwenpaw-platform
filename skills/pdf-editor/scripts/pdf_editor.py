#!/usr/bin/env python3
"""QwenPaw deterministic PDF editor V2.0.

Design goals for text replacement:
- never overwrite the source file by accident;
- prefer the exact source font when it can actually render replacement glyphs;
- detect subset-font false positives by isolated glyph rendering;
- discover exact fonts from a private font registry / system fonts;
- when exact font is unavailable, use a controlled visual-family fallback rather than a broken subset font;
- for equal-length replacements, replace character-by-character at the original character origins,
  preserving baseline, size, color and spacing instead of redrawing the whole line;
- validate each inserted character immediately after drawing it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

try:
    import fitz  # PyMuPDF
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"PyMuPDF is required: {exc}"}, ensure_ascii=False))
    sys.exit(2)

VERSION = "2.0.0-production.1"

ANCHORS = {
    "top-left": (0.07, 0.07),
    "top-center": (0.50, 0.07),
    "top-right": (0.93, 0.07),
    "middle-left": (0.07, 0.50),
    "center": (0.50, 0.50),
    "middle-right": (0.93, 0.50),
    "bottom-left": (0.07, 0.93),
    "bottom-center": (0.50, 0.93),
    "bottom-right": (0.93, 0.93),
}


def _events_enabled() -> bool:
    return str(os.getenv("PDF_EDITOR_PROGRESS", "")).strip().lower() in {"1", "true", "yes", "jsonl"}


def emit_event(event: str, **payload: Any) -> None:
    """Emit machine-readable progress on stderr without corrupting stdout result JSON."""
    if not _events_enabled():
        return
    msg = {"event": event, "tool": "pdf_editor", "version": VERSION, **payload}
    sys.stderr.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def jprint(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def parse_page_string(s: str) -> list[int]:
    out: list[int] = []
    for part in str(s).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a.strip()), int(b.strip())
            step = 1 if b >= a else -1
            out.extend(range(a, b + step, step))
        else:
            out.append(int(part))
    return out


def parse_pages(value: Any, total: int, allow_all: bool = True) -> list[int]:
    if value is None or (allow_all and value == "all"):
        return list(range(total))
    if isinstance(value, int):
        vals = [value]
    elif isinstance(value, str):
        vals = parse_page_string(value)
    elif isinstance(value, list):
        vals = []
        for x in value:
            vals.extend([x] if isinstance(x, int) else parse_page_string(str(x)))
    else:
        raise ValueError(f"Unsupported pages value: {value!r}")
    out: list[int] = []
    for p in vals:
        if p < 1 or p > total:
            raise ValueError(f"Page {p} out of range 1..{total}")
        if p - 1 not in out:
            out.append(p - 1)
    return out


def open_pdf(path: str) -> fitz.Document:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    doc = fitz.open(str(p))
    if doc.needs_pass:
        doc.close()
        raise ValueError("Encrypted/password-protected PDF is not supported")
    if doc.page_count < 1:
        doc.close()
        raise ValueError("PDF has no pages")
    return doc


def safe_save(doc: fitz.Document, input_path: str, output_path: str) -> None:
    inp = Path(input_path).resolve()
    out = Path(output_path).resolve()
    if inp == out:
        raise ValueError("Refusing to overwrite the source PDF. Choose a different output path.")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix=out.stem + ".", suffix=".tmp.pdf", dir=out.parent, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        doc.save(str(tmp_path), garbage=4, deflate=True, clean=True)
        # Re-open before commit. A broken output never replaces the destination.
        chk = fitz.open(str(tmp_path))
        try:
            if chk.page_count < 1:
                raise ValueError("Generated PDF has no pages")
        finally:
            chk.close()
        os.replace(tmp_path, out)
    finally:
        tmp_path.unlink(missing_ok=True)


def validate_pdf(path: str) -> dict[str, Any]:
    doc = fitz.open(path)
    try:
        return {
            "ok": doc.page_count > 0,
            "pages": doc.page_count,
            "size_bytes": Path(path).stat().st_size,
            "pdf_version": doc.metadata.get("format", ""),
        }
    finally:
        doc.close()


def _is_subset_font_name(name: str) -> bool:
    return bool(re.match(r"^[A-Z]{6}\+", (name or "").lstrip("/")))


def classify_pdf(doc: fitz.Document) -> dict[str, Any]:
    """Classify the PDF without OCR. Image-only pages are marked scanned candidates."""
    page_types: list[dict[str, Any]] = []
    subset_fonts: set[str] = set()
    any_forms = False
    text_pages = 0
    image_only_pages = 0
    mixed_pages = 0
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text("text").strip()
        images = page.get_images(full=True)
        widgets = list(page.widgets() or [])
        any_forms = any_forms or bool(widgets)
        for item in page.get_fonts(full=True):
            for n in (str(item[3]) if len(item) > 3 else "", str(item[4]) if len(item) > 4 else ""):
                if _is_subset_font_name(n):
                    subset_fonts.add(n.lstrip("/"))
        if text and images:
            kind = "mixed"
            mixed_pages += 1
        elif text:
            kind = "native_text"
            text_pages += 1
        elif images:
            kind = "scanned_candidate"
            image_only_pages += 1
        else:
            kind = "blank_or_vector"
        page_types.append({
            "page": i + 1,
            "type": kind,
            "text_chars": len(text),
            "images": len(images),
            "form_fields": len(widgets),
        })
    if image_only_pages == doc.page_count:
        primary = "scanned"
    elif (image_only_pages or mixed_pages) and (text_pages or mixed_pages):
        primary = "mixed"
    else:
        primary = "native"
    return {
        "primary_type": primary,
        "has_forms": any_forms,
        "has_subset_fonts": bool(subset_fonts),
        "subset_fonts": sorted(subset_fonts),
        "pages": page_types,
        "ocr_required_for_image_only_pages": image_only_pages > 0,
    }


# --------------------------- font handling ---------------------------

def _normalize_font_name(name: str) -> str:
    name = (name or "").strip().lstrip("/")
    # PDF subset prefix: ABCDEF+SimHei
    if "+" in name and re.match(r"^[A-Z]{6}\+", name):
        name = name.split("+", 1)[1]
    return "".join(ch for ch in name.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


_ALIAS_GROUPS = [
    {"simhei", "黑体", "heiti", "stheiti"},
    {"simsun", "宋体", "songti", "stsong"},
    {"fangsong", "仿宋", "stfangsong"},
    {"kaiti", "楷体", "stkaiti"},
    {"microsoftyahei", "微软雅黑", "yahei"},
    {"dengxian", "等线"},
    {"notosanscjksc", "notosanscjkscregular"},
    {"notoserifcjksc", "notoserifcjkscregular"},
    {"arplsungtilgb", "文鼎pl简报宋"},
    {"arplkaitimgb", "文鼎pl简中楷"},
]


def _aliases(name: str) -> set[str]:
    n = _normalize_font_name(name)
    out = {n} if n else set()
    for group in _ALIAS_GROUPS:
        norm = {_normalize_font_name(x) for x in group}
        if n in norm:
            out |= norm
    return out


def _font_registry_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.getenv("PDF_EDITOR_FONT_DIRS", "")
    if env:
        for item in env.split(os.pathsep):
            if item.strip():
                dirs.append(Path(item.strip()))
    # Private / user-controlled registries first.
    dirs += [
        Path("/app/working/font-registry"),
        Path("/app/working/fonts"),
        Path.home() / ".fonts",
    ]
    uniq: list[Path] = []
    seen = set()
    for d in dirs:
        try:
            r = d.resolve()
        except Exception:
            r = d
        if str(r) not in seen and d.exists():
            seen.add(str(r))
            uniq.append(d)
    return uniq


def _iter_font_files() -> Iterable[Path]:
    seen = set()
    for root in _font_registry_dirs():
        try:
            for p in root.rglob("*"):
                if p.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                    continue
                s = str(p)
                if s not in seen:
                    seen.add(s)
                    yield p
        except Exception:
            continue


def _font_family_from_file(path: Path) -> str:
    if shutil.which("fc-scan"):
        try:
            p = subprocess.run(
                ["fc-scan", "-f", "%{family}\n", str(path)],
                capture_output=True, text=True, timeout=3, check=False,
            )
            line = next((x.strip() for x in p.stdout.splitlines() if x.strip()), "")
            if line:
                return line.split(",", 1)[0]
        except Exception:
            pass
    try:
        return str(fitz.Font(fontfile=str(path)).name or "")
    except Exception:
        return ""


def _isolated_glyph_check(font_obj: fitz.Font, text: str, fontsize: float = 18.0) -> tuple[bool, list[str], dict[str, int]]:
    """Actually render every character on an empty page.

    This catches embedded subset fonts that claim a Unicode glyph but render it blank.
    """
    failed: list[str] = []
    ink: dict[str, int] = {}
    for ch in text:
        if ch.isspace():
            continue
        doc = fitz.open()
        page = doc.new_page(width=90, height=70)
        try:
            tw = fitz.TextWriter(page.rect)
            pt = fitz.Point(12, 42)
            tw.append(pt, ch, font=font_obj, fontsize=fontsize)
            tw.write_text(page, color=(0, 0, 0), overlay=True)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), colorspace=fitz.csGRAY, alpha=False)
            # blank page is 255; count meaningful ink
            cnt = sum(1 for v in pix.samples if v < 240)
            ink[ch] = cnt
            if cnt < 10:
                failed.append(ch)
        except Exception:
            failed.append(ch)
            ink[ch] = 0
        finally:
            doc.close()
    return not failed, failed, ink


def _embedded_font_candidates(doc: fitz.Document, page: fitz.Page, source_name: str, source_span: dict[str, Any], new: str):
    target = _aliases(source_name)
    source_text = str(source_span.get("text", ""))
    size = float(source_span.get("size") or 10.0)
    bbox = fitz.Rect(source_span.get("bbox", (0, 0, 0, 0)))
    candidates = []
    for item in page.get_fonts(full=True):
        if len(item) < 6:
            continue
        xref, ext, ftype, basefont, resource, encoding = item[:6]
        if not xref:
            continue
        try:
            extd = doc.extract_font(int(xref))
            buf = extd[3] if extd and len(extd) >= 4 else b""
            if not buf:
                continue
            fobj = fitz.Font(fontbuffer=buf)
            names = _aliases(str(basefont)) | _aliases(str(resource)) | _aliases(str(extd[0]))
            name_match = bool(target & names) if target else False
            measured = float(fobj.text_length(source_text, fontsize=size)) if source_text else 0.0
            target_w = max(1.0, bbox.width)
            metric_err = abs(measured - target_w) / target_w if measured > 0 else 999.0
            render_ok, failed, ink = _isolated_glyph_check(fobj, new, fontsize=max(12.0, size * 1.6))
            candidates.append({
                "xref": int(xref), "basefont": str(basefont), "resource": str(resource),
                "buffer": buf, "font": fobj, "name_match": name_match,
                "metric_error": metric_err, "render_ok": render_ok,
                "failed": failed, "ink": ink,
            })
        except Exception:
            continue
    candidates.sort(key=lambda c: (0 if c["name_match"] else 1, 0 if c["render_ok"] else 1, c["metric_error"]))
    return candidates


def _find_exact_font_file(source_name: str, new: str) -> tuple[Path | None, str | None, fitz.Font | None]:
    wanted = _aliases(source_name)
    if not wanted:
        return None, None, None

    # fontconfig can find a font quickly, but it always returns *something*, so family must match.
    if shutil.which("fc-match"):
        try:
            p = subprocess.run(
                ["fc-match", "-f", "%{file}\n%{family}\n", source_name],
                capture_output=True, text=True, timeout=3, check=False,
            )
            lines = [x.strip() for x in p.stdout.splitlines() if x.strip()]
            if len(lines) >= 2:
                fp, fam = Path(lines[0]), lines[1].split(",", 1)[0]
                if fp.exists() and wanted & _aliases(fam):
                    fobj = fitz.Font(fontfile=str(fp))
                    ok, _, _ = _isolated_glyph_check(fobj, new)
                    if ok:
                        return fp, fam, fobj
        except Exception:
            pass

    # Explicit scan also finds private registry fonts that are not in fontconfig cache.
    for fp in _iter_font_files():
        fam = _font_family_from_file(fp)
        names = _aliases(fam) | _aliases(fp.stem)
        if not (wanted & names):
            continue
        try:
            fobj = fitz.Font(fontfile=str(fp))
            ok, _, _ = _isolated_glyph_check(fobj, new)
            if ok:
                return fp, fam, fobj
        except Exception:
            continue
    return None, None, None


def _preferred_visual_families(source_name: str, span_flags: int) -> list[str]:
    n = _normalize_font_name(source_name)
    aliases = _aliases(source_name)
    bold = bool(span_flags & 16)
    serif = bool(span_flags & 4)

    def bold_first(reg: str, bld: str) -> list[str]:
        return [bld, reg] if bold else [reg, bld]

    if _normalize_font_name("simhei") in aliases or _normalize_font_name("黑体") in aliases:
        return bold_first("Noto Sans CJK SC", "Noto Sans CJK SC Bold") + ["WenQuanYi Zen Hei", "AR PL KaitiM GB"]
    if _normalize_font_name("microsoftyahei") in aliases or _normalize_font_name("dengxian") in aliases:
        return bold_first("Noto Sans CJK SC", "Noto Sans CJK SC Bold")
    if _normalize_font_name("simsun") in aliases:
        return bold_first("Noto Serif CJK SC", "Noto Serif CJK SC Bold") + ["AR PL SungtiL GB"]
    if _normalize_font_name("fangsong") in aliases:
        return ["AR PL SungtiL GB", "Noto Serif CJK SC"]
    if _normalize_font_name("kaiti") in aliases:
        return ["AR PL KaitiM GB", "Noto Serif CJK SC"]
    if serif:
        return bold_first("Noto Serif CJK SC", "Noto Serif CJK SC Bold") + ["AR PL SungtiL GB"]
    return bold_first("Noto Sans CJK SC", "Noto Sans CJK SC Bold") + ["Noto Serif CJK SC", "AR PL SungtiL GB"]


def _fontconfig_file(family: str) -> tuple[Path | None, str | None]:
    if not shutil.which("fc-match"):
        return None, None
    try:
        p = subprocess.run(
            ["fc-match", "-f", "%{file}\n%{family}\n", family],
            capture_output=True, text=True, timeout=3, check=False,
        )
        lines = [x.strip() for x in p.stdout.splitlines() if x.strip()]
        if len(lines) >= 2:
            fp, fam = Path(lines[0]), lines[1].split(",", 1)[0]
            if fp.exists():
                return fp, fam
    except Exception:
        pass
    return None, None


def _visual_fallback_font(source_name: str, span_flags: int, new: str) -> tuple[str, fitz.Font, str]:
    # Controlled fallback: choose a CJK family with matching serif/sans/style class.
    for requested in _preferred_visual_families(source_name, span_flags):
        fp, fam = _fontconfig_file(requested)
        if not fp:
            continue
        try:
            fobj = fitz.Font(fontfile=str(fp))
            ok, failed, ink = _isolated_glyph_check(fobj, new)
            if ok:
                return str(fp), fobj, f"visual_match:{fam}:{fp}"
        except Exception:
            continue

    # Last-resort PyMuPDF built-in CJK font: still render-verified, never blind.
    try:
        fobj = fitz.Font(fontname="china-s")
        ok, _, _ = _isolated_glyph_check(fobj, new)
        if ok:
            return "china-s", fobj, "visual_match:china-s"
    except Exception:
        pass
    raise ValueError("No render-capable Chinese font is available in the QwenPaw runtime.")


def _resolve_font(doc: fitz.Document, page: fitz.Page, span: dict[str, Any], new: str, font_policy: str) -> dict[str, Any]:
    source_name = str(span.get("font", ""))
    span_flags = int(span.get("flags", 0) or 0)

    # 1. Embedded source font: accept only if actual isolated rendering succeeds.
    embedded = _embedded_font_candidates(doc, page, source_name, span, new)
    for c in embedded:
        if c["render_ok"] and (c["name_match"] or c["metric_error"] <= 0.08):
            return {
                "font": c["font"], "kind": "embedded_exact", "source": f"embedded_exact:{c['basefont']}",
                "fontfile": None, "fontbuffer": c["buffer"], "diagnostics": {"metric_error": c["metric_error"], "ink": c["ink"]},
            }

    # 2. Full exact family from private registry or system.
    fp, fam, fobj = _find_exact_font_file(source_name, new)
    if fp and fobj:
        return {
            "font": fobj, "kind": "system_exact", "source": f"system_exact:{fam}:{fp}",
            "fontfile": str(fp), "fontbuffer": None, "diagnostics": {},
        }

    # exact means exact: fail instead of changing appearance.
    if font_policy in {"exact", "strict", "strict_exact"}:
        failed = []
        if embedded:
            failed = embedded[0].get("failed", [])
        raise ValueError(
            f"Exact source font unavailable for new text. source_font={source_name!r}; "
            f"embedded_missing_or_blank={''.join(failed)!r}. Put the licensed full font in "
            "/app/working/font-registry (or PDF_EDITOR_FONT_DIRS) and retry."
        )

    # 3. Auto mode: visually closest family, render-verified.
    token, fobj, source = _visual_fallback_font(source_name, span_flags, new)
    return {
        "font": fobj, "kind": "visual_match", "source": source,
        "fontfile": token if token != "china-s" else None, "fontbuffer": None, "diagnostics": {},
    }


# --------------------------- char-level text matching ---------------------------

def _raw_spans(page: fitz.Page) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw = page.get_text("rawdict")
    for block in raw.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                text = "".join(str(ch.get("c", "")) for ch in chars)
                item = dict(span)
                item["text"] = text
                item["chars"] = chars
                item["line_dir"] = line.get("dir", (1.0, 0.0))
                out.append(item)
    return out


def _find_span_matches(page: fitz.Page, old: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for span in _raw_spans(page):
        text = span.get("text", "")
        start = 0
        while True:
            pos = text.find(old, start)
            if pos < 0:
                break
            chars = span["chars"][pos:pos + len(old)]
            if len(chars) != len(old):
                break
            matches.append({"span": span, "chars": chars, "start": pos, "end": pos + len(old)})
            start = pos + max(1, len(old))
    return matches


def _pix_diff_pixels(before: fitz.Pixmap, after: fitz.Pixmap, threshold: int = 8) -> tuple[int, int]:
    if before.width != after.width or before.height != after.height or before.n != after.n:
        return -1, 0
    a, b = before.samples, after.samples
    n = max(1, before.n)
    changed = 0
    total = before.width * before.height
    for i in range(0, min(len(a), len(b)), n):
        if any(abs(a[i + c] - b[i + c]) > threshold for c in range(n)):
            changed += 1
    return changed, total


def _apply_text_redactions(page: fitz.Page) -> None:
    try:
        page.apply_redactions(images=0, graphics=0, text=0)
    except TypeError:
        page.apply_redactions()


def _color_tuple(span: dict[str, Any]) -> tuple[float, float, float]:
    try:
        return tuple(fitz.sRGB_to_pdf(int(span.get("color", 0))))
    except Exception:
        return (0.0, 0.0, 0.0)


def _char_advance(chars: list[dict[str, Any]], index: int, span: dict[str, Any]) -> float:
    ch = chars[index]
    origin = fitz.Point(ch.get("origin", (fitz.Rect(ch["bbox"]).x0, fitz.Rect(ch["bbox"]).y1)))
    if index + 1 < len(chars):
        nxt = fitz.Point(chars[index + 1].get("origin", (fitz.Rect(chars[index + 1]["bbox"]).x0, 0)))
        adv = nxt.x - origin.x
        if adv > 0.2:
            return float(adv)
    return max(0.5, fitz.Rect(ch["bbox"]).width)


def _render_insert_char(page: fitz.Page, point: fitz.Point, ch: str, font_obj: fitz.Font, fontsize: float,
                        color: tuple[float, float, float], opacity: float, target_advance: float) -> dict[str, Any]:
    cand_w = max(0.01, float(font_obj.text_length(ch, fontsize=fontsize)))
    sx = target_advance / cand_w if cand_w > 0 else 1.0
    # Extreme scaling means the chosen font is not visually compatible.
    if sx < 0.72 or sx > 1.38:
        raise ValueError(f"Replacement glyph {ch!r} needs unsafe horizontal scale {sx:.3f}")

    # Snapshot a tight area before insertion, then validate immediately after this character.
    clip = fitz.Rect(point.x - 1.0, point.y - fontsize * 1.35, point.x + target_advance + 1.5, point.y + fontsize * 0.35)
    clip &= page.rect
    mat = fitz.Matrix(2.2, 2.2)
    before = page.get_pixmap(matrix=mat, clip=clip, alpha=False)

    writer = fitz.TextWriter(page.rect)
    writer.append(point, ch, font=font_obj, fontsize=fontsize)
    morph = (point, fitz.Matrix(sx, 1.0)) if abs(sx - 1.0) > 0.002 else None
    writer.write_text(page, color=color, opacity=opacity, overlay=True, morph=morph)

    after = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    changed, total = _pix_diff_pixels(before, after)
    minimum = max(8, int(total * 0.006)) if total > 0 else 8
    if changed < minimum:
        raise ValueError(
            f"Inserted glyph {ch!r} did not produce visible pixels (changed={changed}, required={minimum})."
        )
    return {
        "char": ch, "origin": [round(point.x, 3), round(point.y, 3)],
        "target_advance": round(target_advance, 3), "font_advance": round(cand_w, 3),
        "horizontal_scale": round(sx, 5), "changed_pixels": changed,
    }


def _replace_equal_length_match(doc: fitz.Document, page: fitz.Page, match: dict[str, Any], old: str, new: str,
                                *, font_policy: str, background: tuple[float, float, float]) -> dict[str, Any]:
    span = match["span"]
    target_chars = match["chars"]
    all_chars = span["chars"]
    start = int(match["start"])
    fontsize = float(span.get("size") or 10.0)
    color = _color_tuple(span)
    opacity = max(0.0, min(1.0, float(span.get("alpha", 255)) / 255.0))
    resolved = _resolve_font(doc, page, span, new, font_policy)
    font_obj: fitz.Font = resolved["font"]

    # Redact exact character boxes only. This leaves prefix/suffix untouched.
    for ch in target_chars:
        r = fitz.Rect(ch["bbox"])
        pad_x = min(0.18, max(0.04, r.width * 0.01))
        pad_y = min(0.12, max(0.03, r.height * 0.008))
        rr = fitz.Rect(r.x0 - pad_x, r.y0 - pad_y, r.x1 + pad_x, r.y1 + pad_y)
        page.add_redact_annot(rr, fill=background)
    _apply_text_redactions(page)

    inserted = []
    for j, new_ch in enumerate(new):
        src_index = start + j
        src_char = all_chars[src_index]
        point = fitz.Point(src_char.get("origin", (fitz.Rect(src_char["bbox"]).x0, fitz.Rect(src_char["bbox"]).y1)))
        adv = _char_advance(all_chars, src_index, span)
        inserted.append(_render_insert_char(page, point, new_ch, font_obj, fontsize, color, opacity, adv))

    target_bbox = fitz.Rect(target_chars[0]["bbox"])
    for _ch in target_chars[1:]:
        target_bbox |= fitz.Rect(_ch["bbox"])
    return {
        "mode": "char_exact_origin",
        "target_bbox": [round(target_bbox.x0, 3), round(target_bbox.y0, 3), round(target_bbox.x1, 3), round(target_bbox.y1, 3)],
        "source_font": str(span.get("font", "")),
        "font_kind": resolved["kind"],
        "font_source": resolved["source"],
        "font_size": round(fontsize, 3),
        "color": int(span.get("color", 0) or 0),
        "inserted": inserted,
        "style_contract": {
            "baseline_preserved": True,
            "font_size_preserved": True,
            "color_preserved": True,
            "original_char_origins_preserved": True,
            "surrounding_text_redrawn": False,
        },
    }


def _replace_run_match(doc: fitz.Document, page: fitz.Page, match: dict[str, Any], old: str, new: str,
                       *, font_policy: str, background: tuple[float, float, float]) -> dict[str, Any]:
    # Used only when character counts differ. Still keeps baseline/size/color and exact run start.
    span = match["span"]
    target = match["chars"]
    fontsize = float(span.get("size") or 10.0)
    color = _color_tuple(span)
    opacity = max(0.0, min(1.0, float(span.get("alpha", 255)) / 255.0))
    resolved = _resolve_font(doc, page, span, new, font_policy)
    font_obj: fitz.Font = resolved["font"]

    rect = fitz.Rect(target[0]["bbox"])
    for ch in target[1:]:
        rect |= fitz.Rect(ch["bbox"])
    for ch in target:
        page.add_redact_annot(fitz.Rect(ch["bbox"]), fill=background)
    _apply_text_redactions(page)

    point = fitz.Point(target[0].get("origin", (rect.x0, rect.y1)))
    target_w = max(0.5, rect.width)
    raw_w = max(0.01, float(font_obj.text_length(new, fontsize=fontsize)))
    sx = target_w / raw_w
    if sx < 0.72 or sx > 1.38:
        raise ValueError(
            f"Replacement length differs too much to preserve layout safely: target={target_w:.2f}pt new={raw_w:.2f}pt scale={sx:.3f}"
        )

    clip = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 2, rect.y1 + 2) & page.rect
    mat = fitz.Matrix(2.2, 2.2)
    before = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    tw = fitz.TextWriter(page.rect)
    tw.append(point, new, font=font_obj, fontsize=fontsize)
    tw.write_text(page, color=color, opacity=opacity, overlay=True,
                  morph=(point, fitz.Matrix(sx, 1.0)) if abs(sx - 1.0) > 0.002 else None)
    after = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    changed, total = _pix_diff_pixels(before, after)
    if changed < max(12, int(total * 0.006)):
        raise ValueError("Run replacement rendered blank / invisible")
    return {
        "mode": "run_scaled_to_original_box",
        "target_bbox": [round(rect.x0, 3), round(rect.y0, 3), round(rect.x1, 3), round(rect.y1, 3)],
        "source_font": str(span.get("font", "")), "font_kind": resolved["kind"], "font_source": resolved["source"],
        "font_size": round(fontsize, 3), "horizontal_scale": round(sx, 5),
        "style_contract": {"baseline_preserved": True, "font_size_preserved": True, "color_preserved": True, "surrounding_text_redrawn": False},
    }


def _select_occurrences(flat_matches: list[tuple[int, dict[str, Any]]], occurrence: Any) -> list[tuple[int, dict[str, Any]]]:
    if occurrence is None or occurrence == "all":
        return flat_matches
    if isinstance(occurrence, int):
        wanted = [occurrence]
    elif isinstance(occurrence, str):
        wanted = parse_page_string(occurrence)
    elif isinstance(occurrence, list):
        wanted = [int(x) for x in occurrence]
    else:
        raise ValueError("occurrence must be 'all', an integer, a list, or a range string")
    if any(x < 1 or x > len(flat_matches) for x in wanted):
        raise ValueError(f"Occurrence out of range 1..{len(flat_matches)}")
    wanted_set = set(wanted)
    return [item for i, item in enumerate(flat_matches, start=1) if i in wanted_set]


def replace_text(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    old = str(op.get("old", ""))
    new = str(op.get("new", ""))
    if not old:
        raise ValueError("replace_text requires non-empty 'old'")
    pages = parse_pages(op.get("pages", "all"), doc.page_count)
    font_policy = str(op.get("font_policy", "auto")).lower()
    if op.get("allow_compatible_fallback") is False and op.get("font_policy") is None:
        font_policy = "auto"
    background = tuple(op.get("background", [1, 1, 1]))

    source_old_count = sum(doc[idx].get_text("text").count(old) for idx in pages)
    flat: list[tuple[int, dict[str, Any]]] = []
    for idx in pages:
        matches = _find_span_matches(doc[idx], old)
        matches.sort(key=lambda m: (fitz.Rect(m["chars"][0]["bbox"]).y0, fitz.Rect(m["chars"][0]["bbox"]).x0))
        flat.extend((idx, m) for m in matches)
    selected = _select_occurrences(flat, op.get("occurrence", "all"))
    if not selected and bool(op.get("required", True)):
        raise ValueError(f"Text not found in a single text span: {old!r}")

    by_page: dict[int, list[dict[str, Any]]] = {}
    for idx, match in selected:
        by_page.setdefault(idx, []).append(match)
    total = 0
    page_reports = []
    for idx in sorted(by_page):
        page = doc[idx]
        matches = by_page[idx]
        matches.sort(key=lambda m: (fitz.Rect(m["chars"][0]["bbox"]).y0, fitz.Rect(m["chars"][0]["bbox"]).x0), reverse=True)
        edits = []
        emit_event("tool.progress", action="replace_text", page=idx + 1, status="editing", matches=len(matches))
        for m in matches:
            if len(old) == len(new):
                edits.append(_replace_equal_length_match(doc, page, m, old, new, font_policy=font_policy, background=background))
            else:
                edits.append(_replace_run_match(doc, page, m, old, new, font_policy=font_policy, background=background))
            total += 1
        page_reports.append({"page": idx + 1, "matches": len(matches), "edits": edits})

    report.append({
        "action": "replace_text", "old": old, "new": new, "font_policy": font_policy,
        "matches": total, "pages": page_reports, "scope_pages": [p + 1 for p in pages],
        "source_old_count_in_scope": source_old_count, "occurrence": op.get("occurrence", "all")
    })


# --------------------------- other deterministic operations ---------------------------

def rotate_pages(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    deg = int(op.get("degrees", 90))
    if deg % 90:
        raise ValueError("rotate_pages degrees must be a multiple of 90")
    pages = parse_pages(op.get("pages"), doc.page_count, allow_all=False)
    for idx in pages:
        p = doc[idx]
        p.set_rotation((p.rotation + deg) % 360)
    report.append({"action": "rotate_pages", "pages": [p + 1 for p in pages], "degrees": deg})


def delete_pages(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    pages = sorted(parse_pages(op.get("pages"), doc.page_count, allow_all=False), reverse=True)
    if len(pages) >= doc.page_count:
        raise ValueError("Refusing to delete all pages")
    display = [p + 1 for p in pages]
    for idx in pages:
        doc.delete_page(idx)
    report.append({"action": "delete_pages", "pages": sorted(display)})


def _font_name_for(text: str) -> str:
    return "china-s" if any(ord(c) > 127 for c in text) else "helv"


def add_text(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    text = str(op.get("text", ""))
    if not text:
        raise ValueError("add_text requires non-empty text")
    pages = parse_pages(op.get("pages", [1]), doc.page_count)
    fs = float(op.get("font_size", 12))
    color = tuple(op.get("color", [0, 0, 0]))
    pos = op.get("position", "top-right")
    for idx in pages:
        p = doc[idx]
        if isinstance(pos, list) and len(pos) == 2:
            point = fitz.Point(float(pos[0]), float(pos[1]))
        else:
            ax, ay = ANCHORS.get(str(pos), ANCHORS["top-right"])
            point = fitz.Point(p.rect.width * ax, p.rect.height * ay)
        p.insert_text(point, text, fontsize=fs, fontname=_font_name_for(text), color=color, overlay=True)
    report.append({"action": "add_text", "pages": [p + 1 for p in pages], "text": text})


def watermark(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    text = str(op.get("text", ""))
    if not text:
        raise ValueError("watermark requires non-empty text")
    pages = parse_pages(op.get("pages", "all"), doc.page_count)
    fs = float(op.get("font_size", 42))
    opacity = max(0.0, min(1.0, float(op.get("opacity", 0.15))))
    angle = float(op.get("rotate", 45))
    color = tuple(op.get("color", [0.5, 0.5, 0.5]))
    for idx in pages:
        p = doc[idx]
        # show_pdf_page supports arbitrary rotation, unlike insert_textbox's
        # 90-degree-only rotate parameter. The temporary page is transparent.
        stamp = fitz.open()
        sp = stamp.new_page(width=p.rect.width, height=p.rect.height)
        band = fitz.Rect(0, sp.rect.height * 0.42, sp.rect.width, sp.rect.height * 0.58)
        rc = sp.insert_textbox(band, text, fontsize=fs, fontname=_font_name_for(text), color=color,
                               align=1, fill_opacity=opacity, overlay=True)
        if rc < 0:
            stamp.close()
            raise ValueError("Watermark text does not fit the page; reduce font_size")
        p.show_pdf_page(p.rect, stamp, 0, rotate=angle, keep_proportion=False, overlay=True)
        stamp.close()
        emit_event("tool.progress", action="watermark", page=idx + 1, status="edited")
    report.append({"action": "watermark", "pages": [p + 1 for p in pages], "text": text, "rotate": angle, "opacity": opacity})


def page_numbers(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    pages = parse_pages(op.get("pages", "all"), doc.page_count)
    fs = float(op.get("font_size", 9))
    fmt = str(op.get("format", "第 {page} 页 / 共 {total} 页"))
    for idx in pages:
        p = doc[idx]
        text = fmt.format(page=idx + 1, total=doc.page_count)
        rect = fitz.Rect(0, p.rect.height - 30, p.rect.width, p.rect.height - 8)
        p.insert_textbox(rect, text, fontsize=fs, fontname="helv", align=1, color=(0, 0, 0), overlay=True)
    report.append({"action": "page_numbers", "pages": [p + 1 for p in pages]})



def delete_text(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    old = str(op.get("text", op.get("old", "")))
    if not old:
        raise ValueError("delete_text requires non-empty 'text'")
    pages = parse_pages(op.get("pages", "all"), doc.page_count)
    background = tuple(op.get("background", [1, 1, 1]))
    source_count = sum(doc[idx].get_text("text").count(old) for idx in pages)
    flat: list[tuple[int, dict[str, Any]]] = []
    for idx in pages:
        matches = _find_span_matches(doc[idx], old)
        matches.sort(key=lambda m: (fitz.Rect(m["chars"][0]["bbox"]).y0, fitz.Rect(m["chars"][0]["bbox"]).x0))
        flat.extend((idx, m) for m in matches)
    selected = _select_occurrences(flat, op.get("occurrence", "all"))
    if not selected and bool(op.get("required", True)):
        raise ValueError(f"Text not found in a single text span: {old!r}")
    by_page: dict[int, list[dict[str, Any]]] = {}
    for idx, m in selected:
        by_page.setdefault(idx, []).append(m)
    page_reports = []
    total = 0
    for idx in sorted(by_page):
        page = doc[idx]
        rects = []
        for m in sorted(by_page[idx], key=lambda m: fitz.Rect(m["chars"][0]["bbox"]).x0, reverse=True):
            union = fitz.Rect(m["chars"][0]["bbox"])
            for ch in m["chars"]:
                r = fitz.Rect(ch["bbox"])
                union |= r
                page.add_redact_annot(r, fill=background)
            rects.append([round(union.x0,3), round(union.y0,3), round(union.x1,3), round(union.y1,3)])
            total += 1
        _apply_text_redactions(page)
        page_reports.append({"page": idx + 1, "matches": len(by_page[idx]), "target_bboxes": rects})
        emit_event("tool.progress", action="delete_text", page=idx + 1, status="edited")
    report.append({"action":"delete_text","old":old,"matches":total,"pages":page_reports,
                   "scope_pages":[p+1 for p in pages],"source_old_count_in_scope":source_count,
                   "occurrence":op.get("occurrence","all")})


def insert_pages(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    at = int(op.get("at", doc.page_count + 1))
    if at < 1 or at > doc.page_count + 1:
        raise ValueError(f"insert_pages 'at' must be in 1..{doc.page_count + 1}")
    source = op.get("source")
    inserted = 0
    if source:
        src = open_pdf(str(source))
        try:
            src_pages = parse_pages(op.get("source_pages", "all"), src.page_count)
            start_at = at - 1
            for offset, src_idx in enumerate(src_pages):
                doc.insert_pdf(src, from_page=src_idx, to_page=src_idx, start_at=start_at + offset)
                inserted += 1
        finally:
            src.close()
        mode = "from_pdf"
    else:
        count = int(op.get("count", 1))
        if count < 1 or count > 1000:
            raise ValueError("insert_pages count must be 1..1000")
        ref_page = int(op.get("copy_size_from", max(1, min(at, doc.page_count)))) if doc.page_count else 1
        if doc.page_count and not 1 <= ref_page <= doc.page_count:
            raise ValueError(f"copy_size_from out of range 1..{doc.page_count}")
        if "width" in op and "height" in op:
            width, height = float(op["width"]), float(op["height"])
        elif doc.page_count:
            r = doc[ref_page - 1].rect
            width, height = r.width, r.height
        else:
            width, height = 595.0, 842.0
        for n in range(count):
            doc.new_page(pno=(at - 1) + n, width=width, height=height)
            inserted += 1
        mode = "blank"
    report.append({"action":"insert_pages","at":at,"inserted":inserted,"mode":mode})


def reorder_pages(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    order = op.get("order")
    if not isinstance(order, list) or not order:
        raise ValueError("reorder_pages requires non-empty 'order' list")
    parsed = [int(x) for x in order]
    expected = list(range(1, doc.page_count + 1))
    if sorted(parsed) != expected:
        raise ValueError(f"reorder_pages order must be a permutation of 1..{doc.page_count}")
    doc.select([x - 1 for x in parsed])
    report.append({"action":"reorder_pages","order":parsed})


def _image_rect(page: fitz.Page, op: dict[str, Any], image_path: str) -> fitz.Rect:
    if isinstance(op.get("rect"), list) and len(op["rect"]) == 4:
        r = fitz.Rect(*[float(x) for x in op["rect"]])
        if r.is_empty or not page.rect.contains(r):
            raise ValueError("add_image rect must be a non-empty rectangle inside the page")
        return r
    pix = fitz.Pixmap(image_path)
    try:
        aspect = pix.width / max(1, pix.height)
    finally:
        pix = None
    width = float(op.get("width", 120.0))
    height = float(op.get("height", width / max(0.01, aspect)))
    pos = str(op.get("position", "top-right"))
    ax, ay = ANCHORS.get(pos, ANCHORS["top-right"])
    cx, cy = page.rect.width * ax, page.rect.height * ay
    if "left" in pos:
        x0 = cx
    elif "right" in pos:
        x0 = cx - width
    else:
        x0 = cx - width / 2
    if "top" in pos:
        y0 = cy
    elif "bottom" in pos:
        y0 = cy - height
    else:
        y0 = cy - height / 2
    r = fitz.Rect(x0, y0, x0 + width, y0 + height) & page.rect
    if r.is_empty:
        raise ValueError("Computed image rectangle is outside the page")
    return r


def add_image(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    image_path = str(op.get("path", ""))
    if not image_path or not Path(image_path).is_file():
        raise ValueError("add_image requires an existing image 'path'")
    pages = parse_pages(op.get("pages", [1]), doc.page_count)
    placed = []
    for idx in pages:
        page = doc[idx]
        rect = _image_rect(page, op, image_path)
        xref = page.insert_image(rect, filename=image_path, keep_proportion=bool(op.get("keep_proportion", True)), overlay=True)
        placed.append({"page":idx+1,"xref":xref,"rect":[round(rect.x0,2),round(rect.y0,2),round(rect.x1,2),round(rect.y1,2)]})
        emit_event("tool.progress", action="add_image", page=idx + 1, status="edited")
    report.append({"action":"add_image","path":image_path,"placements":placed})


def replace_image(doc: fitz.Document, op: dict[str, Any], report: list[dict[str, Any]]) -> None:
    image_path = str(op.get("path", ""))
    if not image_path or not Path(image_path).is_file():
        raise ValueError("replace_image requires an existing image 'path'")
    xref = op.get("xref")
    if xref is None:
        page_no = int(op.get("page", 1))
        if not 1 <= page_no <= doc.page_count:
            raise ValueError(f"replace_image page out of range 1..{doc.page_count}")
        images = doc[page_no - 1].get_images(full=True)
        image_index = int(op.get("image_index", 1))
        if not 1 <= image_index <= len(images):
            raise ValueError(f"image_index out of range 1..{len(images)} on page {page_no}")
        xref = int(images[image_index - 1][0])
    xref = int(xref)
    referencing = []
    for i in range(doc.page_count):
        if any(int(im[0]) == xref for im in doc[i].get_images(full=True)):
            referencing.append(i + 1)
    if not referencing:
        raise ValueError(f"Image xref {xref} is not referenced by any page")
    requested = op.get("pages")
    if requested is not None and requested != "all":
        selected = [x + 1 for x in parse_pages(requested, doc.page_count)]
        if set(selected) != set(referencing):
            raise ValueError(f"xref {xref} is shared on pages {referencing}; page-specific replacement is unsafe. Select all referencing pages.")
    # xref replacement is document-global for all references to that image object.
    doc[referencing[0] - 1].replace_image(xref, filename=image_path)
    report.append({"action":"replace_image","xref":xref,"pages":referencing,"path":image_path,"scope":"shared_xref"})

OPS = {
    "replace_text": replace_text,
    "delete_text": delete_text,
    "rotate_pages": rotate_pages,
    "delete_pages": delete_pages,
    "insert_pages": insert_pages,
    "reorder_pages": reorder_pages,
    "add_text": add_text,
    "watermark": watermark,
    "page_numbers": page_numbers,
    "add_image": add_image,
    "replace_image": replace_image,
}



def _visual_validate_text_edits(input_path: str, output_path: str, report: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [r for r in report if r.get("action") in {"replace_text", "delete_text"}]
    structural = any(r.get("action") in {"delete_pages", "insert_pages", "reorder_pages"} for r in report)
    if not relevant or structural:
        return {"performed": False, "ok": True, "reason": "no_text_edits_or_structural_page_change"}
    before = fitz.open(input_path)
    after = fitz.open(output_path)
    try:
        if before.page_count != after.page_count:
            return {"performed": True, "ok": False, "page_size_preserved": False, "reason": "page_count_changed"}
        rects_by_page: dict[int, list[fitz.Rect]] = {}
        glyph_ok = True
        for r in relevant:
            if r.get("action") == "replace_text":
                for pr in r.get("pages", []):
                    page_idx = int(pr["page"]) - 1
                    for edit in pr.get("edits", []):
                        if "target_bbox" in edit:
                            rects_by_page.setdefault(page_idx, []).append(fitz.Rect(edit["target_bbox"]))
                        if edit.get("mode") == "char_exact_origin":
                            glyph_ok = glyph_ok and all(int(x.get("changed_pixels",0)) > 0 for x in edit.get("inserted", []))
            else:
                for pr in r.get("pages", []):
                    page_idx = int(pr["page"]) - 1
                    for box in pr.get("target_bboxes", []):
                        rects_by_page.setdefault(page_idx, []).append(fitz.Rect(box))
        page_reports = []
        overall_ok = True
        matrix = fitz.Matrix(1.6, 1.6)
        for page_idx, rects in sorted(rects_by_page.items()):
            pb, pa = before[page_idx], after[page_idx]
            same_size = abs(pb.rect.width-pa.rect.width) < 0.01 and abs(pb.rect.height-pa.rect.height) < 0.01
            if not same_size:
                overall_ok = False
                page_reports.append({"page":page_idx+1,"ok":False,"page_size_preserved":False})
                continue
            a = pb.get_pixmap(matrix=matrix, alpha=False)
            b = pa.get_pixmap(matrix=matrix, alpha=False)
            if a.width != b.width or a.height != b.height or a.n != b.n:
                overall_ok = False
                page_reports.append({"page":page_idx+1,"ok":False,"render_shape_preserved":False})
                continue
            mask_rects = []
            for r in rects:
                rr = fitz.Rect(r.x0-4, r.y0-4, r.x1+4, r.y1+4) & pb.rect
                mask_rects.append((int(rr.x0*1.6), int(rr.y0*1.6), int(rr.x1*1.6)+1, int(rr.y1*1.6)+1))
            changed_target = changed_non = total_target = total_non = 0
            n = a.n
            sa, sb = a.samples, b.samples
            for y in range(a.height):
                row = y * a.width
                for x in range(a.width):
                    inside = any(x0 <= x <= x1 and y0 <= y <= y1 for x0,y0,x1,y1 in mask_rects)
                    i = (row + x) * n
                    changed = any(abs(sa[i+c]-sb[i+c]) > 10 for c in range(n))
                    if inside:
                        total_target += 1
                        changed_target += int(changed)
                    else:
                        total_non += 1
                        changed_non += int(changed)
            non_ratio = changed_non / max(1,total_non)
            target_ratio = changed_target / max(1,total_target)
            ok = non_ratio <= 0.003 and changed_target >= 12
            overall_ok = overall_ok and ok
            page_reports.append({
                "page":page_idx+1,"ok":ok,"page_size_preserved":True,
                "target_changed_pixels":changed_target,"target_diff":round(target_ratio,6),
                "non_target_changed_pixels":changed_non,"non_target_diff":round(non_ratio,6)
            })
        return {"performed": True, "ok": overall_ok and glyph_ok, "glyph_validation": glyph_ok,
                "layout_validation": overall_ok, "page_size_preserved": all(x.get("page_size_preserved",True) for x in page_reports),
                "pages": page_reports}
    finally:
        before.close(); after.close()

def apply_plan(input_path: str, output_path: str, plan: dict[str, Any]) -> dict[str, Any]:
    emit_event("tool.start", action="apply", input=input_path)
    doc = open_pdf(input_path)
    report: list[dict[str, Any]] = []
    try:
        operations = plan.get("operations", [])
        if not isinstance(operations, list) or not operations:
            raise ValueError("Plan requires a non-empty operations list")
        for i, op in enumerate(operations, start=1):
            action = str(op.get("action", ""))
            fn = OPS.get(action)
            if not fn:
                raise ValueError(f"Unsupported action: {action!r}")
            emit_event("tool.progress", action=action, operation=i, total_operations=len(operations), status="start")
            fn(doc, op, report)
            emit_event("tool.progress", action=action, operation=i, total_operations=len(operations), status="done")
        safe_save(doc, input_path, output_path)
    finally:
        doc.close()

    semantic = []
    outdoc = fitz.open(output_path)
    try:
        for r in report:
            action = r.get("action")
            if action not in {"replace_text", "delete_text"}:
                continue
            pages = [int(x) for x in r.get("scope_pages", list(range(1, outdoc.page_count + 1))) if 1 <= int(x) <= outdoc.page_count]
            scoped_text = "\n".join(outdoc[i-1].get_text("text") for i in pages)
            old = r["old"]
            old_remaining = scoped_text.count(old)
            expected_remaining = max(0, int(r.get("source_old_count_in_scope", r.get("matches",0))) - int(r.get("matches",0)))
            if action == "replace_text":
                new = r["new"]
                new_count = scoped_text.count(new)
                ok = old_remaining == expected_remaining and (new == old or new_count >= int(r.get("matches",0)))
                semantic.append({"action":action,"old":old,"new":new,"old_remaining":old_remaining,
                                 "expected_old_remaining":expected_remaining,"new_count":new_count,"ok":ok})
            else:
                ok = old_remaining == expected_remaining
                semantic.append({"action":action,"old":old,"old_remaining":old_remaining,
                                 "expected_old_remaining":expected_remaining,"ok":ok})
    finally:
        outdoc.close()
    semantic_ok = all(x["ok"] for x in semantic) if semantic else True
    if not semantic_ok:
        raise ValueError(f"Post-save semantic validation failed: {semantic}")
    visual = _visual_validate_text_edits(input_path, output_path, report)
    if visual.get("performed") and not visual.get("ok"):
        raise ValueError(f"Post-save visual validation failed: {visual}")
    validation = validate_pdf(output_path)
    validation.update({"semantic_ok": semantic_ok, "visual_ok": bool(visual.get("ok", True)), "visual": visual})
    result = {"ok": True, "version": VERSION, "input": input_path, "output": output_path,
              "operations": report, "validation": validation, "semantic_validation": semantic}
    emit_event("file.ready", output=output_path)
    emit_event("tool.result", ok=True, output=output_path)
    return result


def cmd_info(args):
    doc = open_pdf(args.input)
    try:
        pages = []
        for i in range(doc.page_count):
            p = doc[i]
            fonts = []
            for sp in _raw_spans(p):
                key = (sp.get("font", ""), sp.get("size", 0), sp.get("flags", 0))
                if key not in fonts:
                    fonts.append(key)
            pages.append({
                "page": i + 1, "width": round(p.rect.width, 2), "height": round(p.rect.height, 2),
                "rotation": p.rotation, "text_preview": p.get_text("text")[:350].replace("\n", " "),
                "fonts": [{"font": a, "size": b, "flags": c} for a, b, c in fonts[:20]],
            })
        jprint({"ok": True, "version": VERSION, "input": args.input, "pages_count": doc.page_count,
                "classification": classify_pdf(doc),
                "font_registry_dirs": [str(x) for x in _font_registry_dirs()], "pages": pages})
    finally:
        doc.close()


def cmd_apply(args):
    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)
    jprint(apply_plan(args.input, args.output, plan))


def _save_new_document(doc: fitz.Document, output_path: str, forbidden_inputs: list[str]) -> None:
    out = Path(output_path).resolve()
    forbidden = {Path(x).resolve() for x in forbidden_inputs}
    if out in forbidden:
        raise ValueError("Refusing to overwrite a source PDF")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix=out.stem + ".", suffix=".tmp.pdf", dir=out.parent, delete=False)
    tmp_path = Path(tmp.name); tmp.close()
    try:
        doc.save(str(tmp_path), garbage=4, deflate=True, clean=True)
        chk = fitz.open(str(tmp_path))
        try:
            if chk.page_count < 1:
                raise ValueError("Generated PDF has no pages")
        finally:
            chk.close()
        os.replace(tmp_path, out)
    finally:
        tmp_path.unlink(missing_ok=True)


def cmd_merge(args):
    emit_event("tool.start", action="merge", inputs=args.inputs)
    out = fitz.open()
    try:
        for n, path in enumerate(args.inputs, start=1):
            src = open_pdf(path)
            try:
                out.insert_pdf(src)
            finally:
                src.close()
            emit_event("tool.progress", action="merge", file=n, total_files=len(args.inputs), status="done")
        if out.page_count < 1:
            raise ValueError("No pages to merge")
        _save_new_document(out, args.output, args.inputs)
    finally:
        out.close()
    result={"ok": True, "version": VERSION, "action": "merge", "output": args.output, "validation": validate_pdf(args.output)}
    emit_event("file.ready", output=args.output); emit_event("tool.result", ok=True, output=args.output)
    jprint(result)


def cmd_extract(args):
    emit_event("tool.start", action="extract", input=args.input)
    src = open_pdf(args.input)
    out = fitz.open()
    try:
        pages = parse_pages(args.pages, src.page_count, allow_all=False)
        for idx in pages:
            out.insert_pdf(src, from_page=idx, to_page=idx)
        _save_new_document(out, args.output, [args.input])
    finally:
        out.close(); src.close()
    result={"ok": True, "version": VERSION, "action": "extract_pages", "pages": [p + 1 for p in pages],
            "output": args.output, "validation": validate_pdf(args.output)}
    emit_event("file.ready", output=args.output); emit_event("tool.result", ok=True, output=args.output)
    jprint(result)



def cmd_split(args):
    src = open_pdf(args.input)
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = []
    try:
        groups: list[list[int]] = []
        if args.ranges:
            for group in args.ranges.split(";"):
                groups.append(parse_pages(group.strip(), src.page_count, allow_all=False))
        else:
            chunk = max(1, int(args.chunk_size or 1))
            all_pages = list(range(src.page_count))
            groups = [all_pages[i:i+chunk] for i in range(0, len(all_pages), chunk)]
        stem = Path(args.input).stem
        for n, pages in enumerate(groups, start=1):
            out = fitz.open()
            try:
                for idx in pages:
                    out.insert_pdf(src, from_page=idx, to_page=idx)
                path = outdir / f"{stem}_part_{n:03d}.pdf"
                out.save(str(path), garbage=4, deflate=True, clean=True)
                outputs.append({"path":str(path),"pages":[x+1 for x in pages],"validation":validate_pdf(str(path))})
            finally:
                out.close()
    finally:
        src.close()
    jprint({"ok":True,"version":VERSION,"action":"split","outputs":outputs})

def build_parser():
    p = argparse.ArgumentParser(description=f"QwenPaw deterministic PDF editor V{VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info"); s.add_argument("--input", required=True); s.set_defaults(func=cmd_info)
    s = sub.add_parser("apply"); s.add_argument("--input", required=True); s.add_argument("--output", required=True); s.add_argument("--plan", required=True); s.set_defaults(func=cmd_apply)
    s = sub.add_parser("merge"); s.add_argument("--output", required=True); s.add_argument("inputs", nargs="+"); s.set_defaults(func=cmd_merge)
    s = sub.add_parser("extract"); s.add_argument("--input", required=True); s.add_argument("--output", required=True); s.add_argument("--pages", required=True); s.set_defaults(func=cmd_extract)
    s = sub.add_parser("split"); s.add_argument("--input", required=True); s.add_argument("--output-dir", required=True); s.add_argument("--ranges"); s.add_argument("--chunk-size", type=int, default=1); s.set_defaults(func=cmd_split)
    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except Exception as exc:
        emit_event("message.error", error=str(exc), error_type=type(exc).__name__)
        jprint({"ok": False, "version": VERSION, "error": str(exc), "type": type(exc).__name__})
        sys.exit(1)


if __name__ == "__main__":
    main()
