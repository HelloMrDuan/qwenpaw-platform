"""Emit a non-secret JSON health report for shared productivity Runtimes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from core.productivity_skills.capabilities import CapabilityResolver


CAPABILITIES = (
    "opencv",
    "ffmpeg",
    "tesseract",
    "paddleocr",
    "asr",
    "background_removal",
    "realesrgan",
    "gfpgan",
    "codeformer",
    "lama",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-test",
        action="store_true",
        help="load ASR models and execute a minimal rembg inference",
    )
    args = parser.parse_args()
    report = CapabilityResolver().resolve_many(
        CAPABILITIES,
        runtime_test=args.runtime_test,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["status"] != "RUNTIME_ERROR" for item in report.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
