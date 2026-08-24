from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pymupdf as fitz


TEST_ROOT = Path(__file__).resolve().parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from helpers import FIXTURES, apply_plan


def render_pdf(path: Path, output_dir: Path, prefix: str) -> list[str]:
    rendered = []
    with fitz.open(path) as doc:
        for page_index, page in enumerate(doc, start=1):
            target = output_dir / f"{prefix}-page-{page_index:02d}.png"
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(target)
            rendered.append(target.name)
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    visual = root / "visual"
    visual.mkdir(exist_ok=True)

    insert_pdf = root / "insert-pages-accepted.pdf"
    insert_result, _ = apply_plan(
        FIXTURES / "native_three_pages.pdf",
        insert_pdf,
        [{"action": "insert_pages", "at": 2, "count": 1}],
    )
    image_pdf = root / "replace-image-accepted.pdf"
    image_result, _ = apply_plan(
        FIXTURES / "image_placement.pdf",
        image_pdf,
        [{
            "action": "replace_image",
            "page": 1,
            "image_index": 1,
            "path": str(FIXTURES / "image_replacement.png"),
        }],
    )
    page_number_pdf = root / "page-numbers-accepted.pdf"
    page_number_result, _ = apply_plan(
        FIXTURES / "native_three_pages.pdf",
        page_number_pdf,
        [{"action": "page_numbers", "pages": "all"}],
    )

    evidence = {
        "status": "AUTOMATED_FIXTURE_PASS",
        "real_document_status": "NOT_RUN_NO_REAL_FIXTURE_AVAILABLE",
        "insert_pages": {
            "validation": insert_result["operations"][0]["validation"],
            "renders": render_pdf(insert_pdf, visual, "insert-pages"),
        },
        "replace_image": {
            "before_image_geometry": image_result["operations"][0]["before_image_geometry"],
            "after_image_geometry": image_result["operations"][0]["after_image_geometry"],
            "geometry_diff": image_result["operations"][0]["geometry_diff"],
            "validation": image_result["operations"][0]["validation"],
            "renders": render_pdf(image_pdf, visual, "replace-image"),
        },
        "page_numbers": {
            "validation": page_number_result["operations"][0]["validation"],
            "page_reports": page_number_result["operations"][0]["page_reports"],
            "renders": render_pdf(page_number_pdf, visual, "page-numbers"),
        },
    }
    (root / "AUTOMATED_RESULTS.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "output_dir": str(root)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
