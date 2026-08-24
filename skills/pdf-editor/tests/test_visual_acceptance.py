from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import pymupdf as fitz

from helpers import FIXTURES, apply_plan, normalized_text, page_render_hash


class P0VisualAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pdf-editor-v12-visual-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def test_inserted_page_is_real_and_original_pages_move_without_change(self) -> None:
        source = FIXTURES / "native_three_pages.pdf"
        output = self.output / "inserted.pdf"
        with fitz.open(source) as before:
            hashes = [page_render_hash(page) for page in before]
        result, _ = apply_plan(
            source, output, [{"action": "insert_pages", "at": 2, "count": 1}]
        )
        with fitz.open(output) as after:
            self.assertEqual(after.page_count, 4)
            self.assertEqual(page_render_hash(after[0]), hashes[0])
            self.assertEqual(page_render_hash(after[2]), hashes[1])
            self.assertEqual(page_render_hash(after[3]), hashes[2])
            self.assertEqual(normalized_text(after[1]).strip(), "")
            self.assertGreater(after.page_xref(1), 0)
            self.assertGreater(len(after[1].get_pixmap(matrix=fitz.Matrix(2, 2)).samples), 0)
        validation = result["operations"][0]["validation"]
        self.assertTrue(validation["page_tree_ok"])
        self.assertTrue(validation["order_ok"])

    def test_replace_image_preserves_bbox_transform_and_non_target_region(self) -> None:
        output = self.output / "replaced.pdf"
        result, _ = apply_plan(
            FIXTURES / "image_placement.pdf",
            output,
            [{
                "action": "replace_image",
                "page": 1,
                "image_index": 1,
                "path": str(FIXTURES / "image_replacement.png"),
            }],
        )
        operation = result["operations"][0]
        self.assertEqual(
            operation["before_image_geometry"][0]["bbox"],
            operation["after_image_geometry"][0]["bbox"],
        )
        self.assertEqual(
            operation["before_image_geometry"][0]["transform"],
            operation["after_image_geometry"][0]["transform"],
        )
        visual = operation["validation"]["page_visual"][0]
        self.assertGreater(visual["target_diff"], 0.01)
        self.assertLessEqual(visual["non_target_diff"], 0.003)
        self.assertTrue(operation["validation"]["no_overlay"])

    def test_page_number_chinese_glyphs_have_rendered_ink_after_reopen(self) -> None:
        output = self.output / "numbered.pdf"
        result, _ = apply_plan(
            FIXTURES / "native_three_pages.pdf",
            output,
            [{"action": "page_numbers", "pages": "all"}],
        )
        operation = result["operations"][0]
        for page_report in operation["page_reports"]:
            glyphs = page_report["glyph_validation"]["glyphs"]
            for required in ("第", "页", "共"):
                self.assertTrue(glyphs[required])
                self.assertTrue(all(item["ink_pixels"] >= 8 for item in glyphs[required]))
        reopened = result["validation"]["operations"]["checks"][0]
        self.assertTrue(reopened["ok"])


if __name__ == "__main__":
    unittest.main()
