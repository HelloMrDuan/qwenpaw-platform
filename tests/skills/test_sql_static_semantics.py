from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.productivity_skills import execute_skill


class SqlStaticSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def analyze(self, sql: str):
        return execute_skill(
            "sql-diagnostics",
            {
                "operation": "analyze",
                "dialect": "oracle",
                "sql": sql,
                "output_dir": str(self.output_dir),
            },
        )

    @staticmethod
    def group_findings(response):
        return [
            finding
            for finding in response["data"]["findings"]
            if finding["location"] == "GROUP BY"
        ]

    def test_oracle_group_by_reports_non_aggregated_column(self):
        response = self.analyze(
            "SELECT A.ID, A.NAME, COUNT(*) FROM TEST A GROUP BY A.ID;"
        )
        findings = self.group_findings(response)

        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0]["finding"],
            "non-aggregated column A.NAME is not included in GROUP BY",
        )
        self.assertIn("GROUP BY A.ID, A.NAME", findings[0]["minimal_fix"])
        self.assertIn("GROUP BY A.ID, A.NAME", response["data"]["recommended_sql"])

    def test_correct_group_by_has_no_false_positive(self):
        response = self.analyze(
            "SELECT A.ID, A.NAME, COUNT(*) FROM TEST A GROUP BY A.ID, A.NAME"
        )
        self.assertEqual(self.group_findings(response), [])

    def test_standard_aggregate_functions_do_not_require_grouping(self):
        response = self.analyze(
            "SELECT A.ID, COUNT(*), SUM(A.AMOUNT), MAX(A.HIGH), "
            "MIN(A.LOW), AVG(A.SCORE) FROM TEST A GROUP BY A.ID"
        )
        self.assertEqual(self.group_findings(response), [])

    def test_select_alias_is_not_mistaken_for_grouped_expression(self):
        response = self.analyze(
            "SELECT A.ID AS ITEM_ID, A.NAME DISPLAY_NAME, COUNT(*) AS TOTAL "
            "FROM TEST A GROUP BY A.ID, A.NAME ORDER BY ITEM_ID"
        )
        self.assertEqual(self.group_findings(response), [])
        self.assertFalse(
            any(
                finding["location"] == "DISTINCT/ORDER BY"
                for finding in response["data"]["findings"]
            )
        )

    def test_distinct_order_by_expression_must_be_selected(self):
        response = self.analyze(
            "SELECT DISTINCT A.ID FROM TEST A ORDER BY A.NAME"
        )
        self.assertTrue(
            any(
                finding["location"] == "DISTINCT/ORDER BY"
                for finding in response["data"]["findings"]
            )
        )

    def test_having_non_aggregate_column_must_be_grouped(self):
        response = self.analyze(
            "SELECT A.ID, COUNT(*) FROM TEST A GROUP BY A.ID HAVING A.NAME = 'X'"
        )
        self.assertTrue(
            any(
                finding["location"] == "HAVING"
                and "A.NAME" in finding["finding"]
                for finding in response["data"]["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
