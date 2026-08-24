from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pymupdf as fitz


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ENGINE = SKILL_ROOT / "scripts" / "pdf_editor.py"


def run_editor(*arguments: object, expect_ok: bool = True):
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    process = subprocess.run(
        [sys.executable, str(ENGINE), *map(str, arguments)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        env=environment,
        check=False,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"non-json stdout={process.stdout!r} stderr={process.stderr!r}"
        ) from exc
    if expect_ok:
        assert process.returncode == 0 and result.get("ok") is True, (
            process.returncode,
            result,
            process.stderr,
        )
    else:
        assert process.returncode != 0 and result.get("ok") is False
    return result, process.stderr


def apply_plan(input_path: Path, output_path: Path, operations: list[dict]):
    plan_path = output_path.with_suffix(".plan.json")
    plan_path.write_text(
        json.dumps({"operations": operations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_editor(
        "apply",
        "--input",
        input_path,
        "--output",
        output_path,
        "--plan",
        plan_path,
    )


def page_render_hash(page: fitz.Page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), colorspace=fitz.csGRAY, alpha=False)
    return hashlib.sha256(pix.samples).hexdigest()


def normalized_text(page: fitz.Page) -> str:
    return page.get_text("text").replace("\u00a0", " ").replace("\u202f", " ")


def assert_pass_contract(testcase, result: dict) -> None:
    validation = result["validation"]
    for field in (
        "operation_execution_ok",
        "reopen_ok",
        "semantic_ok",
        "visual_ok",
        "geometry_layout_ok",
    ):
        testcase.assertIs(validation.get(field), True, field)
