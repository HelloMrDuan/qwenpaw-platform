from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import pymupdf as fitz

from helpers import FIXTURES, apply_plan, assert_pass_contract, normalized_text, run_editor


class PDFEditorV12RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="pdf-editor-v12-regression-")
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.source = FIXTURES / "native_three_pages.pdf"

    def test_01_pdf_type_classification(self) -> None:
        result, _ = run_editor("info", "--input", self.source)
        self.assertEqual(result["classification"]["primary_type"], "native")
        scanned, _ = run_editor("info", "--input", FIXTURES / "scanned_candidate.pdf")
        self.assertEqual(scanned["classification"]["primary_type"], "scanned")

    def test_02_replace_all_text(self) -> None:
        output = self.output / "02-replace-all.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "replace_text", "pages": "all", "old": "乌审旗", "new": "杭锦旗"}],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            text = "\n".join(normalized_text(page) for page in doc)
        self.assertNotIn("乌审旗", text)
        self.assertEqual(text.count("杭锦旗"), 3)

    def test_03_replace_nth_occurrence(self) -> None:
        output = self.output / "03-replace-nth.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{
                "action": "replace_text",
                "pages": [2],
                "old": "乌审旗",
                "new": "杭锦旗",
                "occurrence": 1,
            }],
        )
        assert_pass_contract(self, result)
        semantic = result["semantic_validation"][0]
        self.assertEqual(semantic["old_remaining"], 1)
        self.assertEqual(semantic["new_count"], 1)

    def test_04_delete_text(self) -> None:
        output = self.output / "04-delete-text.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "delete_text", "pages": [1], "text": "DELETE ME"}],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertNotIn("DELETE ME", normalized_text(doc[0]))

    def test_05_delete_page(self) -> None:
        output = self.output / "05-delete-page.pdf"
        result, _ = apply_plan(
            self.source, output, [{"action": "delete_pages", "pages": [2]}]
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertEqual(doc.page_count, 2)
            self.assertIn("ORIGINAL PAGE 1", normalized_text(doc[0]))
            self.assertIn("ORIGINAL PAGE 3", normalized_text(doc[1]))

    def test_06_insert_page(self) -> None:
        output = self.output / "06-insert-page.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "insert_pages", "at": 2, "count": 1, "copy_size_from": 1}],
        )
        assert_pass_contract(self, result)
        operation = result["operations"][0]
        self.assertTrue(operation["validation"]["page_tree_ok"])
        self.assertTrue(operation["validation"]["independent_render_ok"])
        with fitz.open(output) as doc:
            self.assertEqual(doc.page_count, 4)
            self.assertEqual(normalized_text(doc[1]).strip(), "")
            self.assertIn("ORIGINAL PAGE 1", normalized_text(doc[0]))
            self.assertIn("ORIGINAL PAGE 2", normalized_text(doc[2]))
            self.assertIn("ORIGINAL PAGE 3", normalized_text(doc[3]))
            self.assertGreater(doc.page_xref(1), 0)
            self.assertGreater(len(doc[1].get_pixmap().samples), 0)

    def test_07_reorder_pages(self) -> None:
        output = self.output / "07-reorder.pdf"
        result, _ = apply_plan(
            self.source, output, [{"action": "reorder_pages", "order": [3, 1, 2]}]
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertIn("ORIGINAL PAGE 3", normalized_text(doc[0]))
            self.assertIn("ORIGINAL PAGE 1", normalized_text(doc[1]))
            self.assertIn("ORIGINAL PAGE 2", normalized_text(doc[2]))

    def test_08_rotate_page(self) -> None:
        output = self.output / "08-rotate.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "rotate_pages", "pages": [2], "degrees": 90}],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertEqual(doc[1].rotation, 90)

    def test_09_split_pdf(self) -> None:
        output_dir = self.output / "09-split"
        result, _ = run_editor(
            "split", "--input", self.source, "--output-dir", output_dir, "--chunk-size", 2
        )
        self.assertEqual([item["validation"]["pages"] for item in result["outputs"]], [2, 1])

    def test_10_merge_pdf(self) -> None:
        output = self.output / "10-merge.pdf"
        result, _ = run_editor("merge", "--output", output, self.source, self.source)
        self.assertEqual(result["validation"]["pages"], 6)
        with fitz.open(output) as doc:
            self.assertEqual(doc.page_count, 6)

    def test_11_extract_pages(self) -> None:
        output = self.output / "11-extract.pdf"
        result, _ = run_editor(
            "extract", "--input", self.source, "--output", output, "--pages", "1,3"
        )
        self.assertEqual(result["validation"]["pages"], 2)
        with fitz.open(output) as doc:
            self.assertIn("ORIGINAL PAGE 1", normalized_text(doc[0]))
            self.assertIn("ORIGINAL PAGE 3", normalized_text(doc[1]))

    def test_12_add_text(self) -> None:
        output = self.output / "12-add-text.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "add_text", "pages": [1], "text": "ADDED", "position": [72, 320]}],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertIn("ADDED", normalized_text(doc[0]))

    def test_13_add_image(self) -> None:
        output = self.output / "13-add-image.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{
                "action": "add_image",
                "pages": [1],
                "path": str(FIXTURES / "image_original.png"),
                "rect": [320, 300, 500, 375],
            }],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertGreaterEqual(len(doc[0].get_image_info(xrefs=True)), 1)

    def test_14_replace_image(self) -> None:
        output = self.output / "14-replace-image.pdf"
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
        assert_pass_contract(self, result)
        operation = result["operations"][0]
        self.assertTrue(operation["validation"]["geometry_ok"])
        self.assertTrue(operation["validation"]["old_content_absent"])
        self.assertTrue(operation["validation"]["new_content_present"])
        self.assertTrue(operation["validation"]["no_overlay"])
        self.assertEqual(operation["geometry_diff"][0]["bbox_max_abs"], 0.0)
        self.assertEqual(operation["geometry_diff"][0]["transform_max_abs"], 0.0)

    def test_15_watermark(self) -> None:
        output = self.output / "15-watermark.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "watermark", "pages": "all", "text": "QA", "font_size": 24}],
        )
        assert_pass_contract(self, result)
        with fitz.open(output) as doc:
            self.assertTrue(all("QA" in normalized_text(page) for page in doc))

    def test_16_page_numbers(self) -> None:
        output = self.output / "16-page-numbers.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{
                "action": "page_numbers",
                "pages": "all",
                "format": "第 {page} 页 / 共 {total} 页",
                "font_size": 9,
            }],
        )
        assert_pass_contract(self, result)
        operation = result["operations"][0]
        self.assertTrue(operation["validation"]["ok"])
        with fitz.open(output) as doc:
            for index, page in enumerate(doc, start=1):
                self.assertIn(f"第 {index} 页 / 共 3 页", normalized_text(page))

    def test_17_visual_acceptance(self) -> None:
        output = self.output / "17-visual.pdf"
        result, _ = apply_plan(
            self.source,
            output,
            [{"action": "replace_text", "pages": "all", "old": "乌审旗", "new": "杭锦旗"}],
        )
        assert_pass_contract(self, result)
        visual = result["validation"]["visual"]
        self.assertTrue(visual["performed"])
        self.assertTrue(visual["glyph_validation"])
        self.assertTrue(all(item["non_target_diff"] <= 0.003 for item in visual["pages"]))
        self.assertTrue(result["validation"]["post_save_snapshot"]["ok"])


if __name__ == "__main__":
    unittest.main()
