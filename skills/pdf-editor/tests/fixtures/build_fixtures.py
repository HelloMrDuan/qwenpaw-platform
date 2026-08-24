"""Build small deterministic PDF Editor fixtures.

The generated files are synthetic automation fixtures, not real-document
acceptance evidence.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent


def _font_path() -> Path:
    candidates = [
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/Noto Sans SC (TrueType).otf"),
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError("A complete Noto CJK font is required to regenerate fixtures")


def _write_text(page: fitz.Page, point: tuple[float, float], text: str, size: float) -> None:
    font = fitz.Font(fontfile=str(_font_path()))
    writer = fitz.TextWriter(page.rect)
    writer.append(point, text, font=font, fontsize=size)
    writer.write_text(page, color=(0, 0, 0), overlay=True)


def _make_png(path: Path, width: int, height: int, primary: int, secondary: int) -> None:
    def rgb(value: int) -> tuple[int, int, int]:
        return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)

    image = Image.new("RGB", (width, height), rgb(primary))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
        fill=rgb(secondary),
    )
    draw.line((0, 0, width - 1, height - 1), fill=(255, 255, 255), width=3)
    image.save(path)


def build() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    original = ROOT / "image_original.png"
    replacement = ROOT / "image_replacement.png"
    _make_png(original, 120, 50, 0xCC3333, 0xFFE066)
    _make_png(replacement, 55, 130, 0x2855CC, 0x66E0CC)

    doc = fitz.open()
    colors = [(0.95, 0.85, 0.85), (0.85, 0.95, 0.85), (0.85, 0.85, 0.95)]
    chinese = ["客户地址：乌审旗刘总", "第二页 乌审旗 测试 乌审旗", "第三页 保持不变"]
    for number in range(1, 4):
        page = doc.new_page(width=595, height=842)
        page.draw_rect(fitz.Rect(36, 36, 559, 806), fill=colors[number - 1], color=colors[number - 1])
        page.draw_rect(
            fitz.Rect(60, 60, 220, 150),
            fill=(number / 4, 0.15, 0.15),
            color=(number / 4, 0.15, 0.15),
        )
        page.insert_text((72, 190), f"ORIGINAL PAGE {number}", fontsize=18, fontname="helv")
        _write_text(page, (72, 230), chinese[number - 1], 14)
        if number == 1:
            page.insert_text((72, 270), "DELETE ME", fontsize=12, fontname="helv")
    doc.subset_fonts()
    doc.save(ROOT / "native_three_pages.pdf", garbage=4, deflate=True)
    doc.close()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 90), "IMAGE PLACEMENT FIXTURE", fontsize=16, fontname="helv")
    page.draw_rect(fitz.Rect(40, 300, 180, 360), fill=(0.2, 0.7, 0.2), color=(0.2, 0.7, 0.2))
    page.insert_image(
        fitz.Rect(210, 180, 450, 280),
        filename=original,
        keep_proportion=False,
        overlay=True,
    )
    doc.save(ROOT / "image_placement.pdf", garbage=4, deflate=True)
    doc.close()

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=original, keep_proportion=False)
    doc.save(ROOT / "scanned_candidate.pdf", garbage=4, deflate=True)
    doc.close()


if __name__ == "__main__":
    build()
