"""Generate deterministic source scaffolds for the Phase 15 Skill Pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SKILLS = {
    "image-toolkit": {
        "description": "Deterministic Pillow-based image inspection, conversion, geometry, metadata, batch and duplicate operations without AI.",
        "capabilities": {"required": ["pillow"], "optional": ["opencv", "imagemagick"], "runtime": []},
        "operations": ["info", "exif", "hash", "convert", "resize", "crop", "rotate", "flip", "compress", "quality", "dpi", "strip_exif", "alpha", "concat", "split", "to_pdf", "duplicates", "batch_convert", "batch_compress"],
    },
    "photo-restoration": {
        "description": "Traditional old-photo restoration pipeline with explicit optional AI restoration Runtime stages.",
        "capabilities": {"required": ["pillow"], "optional": ["opencv"], "runtime": ["realesrgan", "gfpgan", "codeformer", "lama", "colorization"]},
        "operations": ["inspect", "pipeline", "comparison", "batch"],
    },
    "advanced-ocr": {
        "description": "Image OCR orchestration with text, confidence, bounding boxes and structured output; PDF OCR stays built-in.",
        "capabilities": {"required": [], "optional": ["tesseract", "openpyxl"], "runtime": ["paddleocr"]},
        "operations": ["ocr", "batch", "layout", "table", "json", "markdown", "txt", "csv", "xlsx"],
    },
    "media-transcriber": {
        "description": "Media inspection/audio extraction plus ASR transcript and meeting-report orchestration.",
        "capabilities": {"required": [], "optional": ["ffmpeg"], "runtime": ["asr"]},
        "operations": ["inspect", "extract_audio", "transcribe", "summarize_transcript", "export_transcript"],
    },
    "image-background-tools": {
        "description": "Safe solid-background removal, replacement, blur and subject crop with optional segmentation Runtime.",
        "capabilities": {"required": ["pillow"], "optional": ["opencv"], "runtime": ["background_removal"]},
        "operations": ["remove_solid", "transparent", "white", "black", "color", "replace", "blur", "crop_subject", "segment", "alpha_matting"],
    },
    "image-quality-enhancer": {
        "description": "Traditional resize, denoise, sharpen, gamma, contrast and white-balance enhancement with optional AI super-resolution.",
        "capabilities": {"required": ["pillow"], "optional": ["opencv"], "runtime": ["realesrgan"]},
        "operations": ["enhance", "upscale_2x", "upscale_4x", "denoise", "sharpen", "gamma", "white_balance", "batch"],
    },
    "sql-diagnostics": {
        "description": "Read-only Oracle, MySQL, PostgreSQL and SQL Server SQL/error diagnosis with risk-aware minimal fixes.",
        "capabilities": {"required": [], "optional": ["sqlparse"], "runtime": []},
        "operations": ["analyze", "format", "explain_plan", "diagnose_error"],
    },
    "log-incident-analyzer": {
        "description": "Chronological multi-stack incident analysis, clustering, root-cause chain and evidence report.",
        "capabilities": {"required": [], "optional": [], "runtime": []},
        "operations": ["analyze", "cluster", "timeline", "correlate"],
    },
    "api-debugger": {
        "description": "Offline HTTP evidence diagnosis and reproducible curl/Python/Java request generation.",
        "capabilities": {"required": [], "optional": ["curl"], "runtime": []},
        "operations": ["analyze", "generate_curl", "generate_python", "generate_java"],
    },
    "ops-troubleshooter": {
        "description": "Focused observe-hypothesize-verify troubleshooting plans for Linux, containers, Kubernetes, services and GPU.",
        "capabilities": {"required": [], "optional": ["docker", "kubectl", "nvidia-smi"], "runtime": []},
        "operations": ["analyze", "plan_checks"],
    },
    "network-diagnostics": {
        "description": "Windows/Linux DNS, route, TCP, TLS, HTTP, proxy and IPv4/IPv6 verification plans.",
        "capabilities": {"required": [], "optional": ["curl", "dig", "nslookup", "traceroute"], "runtime": []},
        "operations": ["plan", "analyze_evidence"],
    },
    "config-diagnostics": {
        "description": "Secret-redacted JSON, YAML, XML, properties, env, INI and service configuration validation.",
        "capabilities": {"required": [], "optional": ["yaml"], "runtime": []},
        "operations": ["validate", "security_scan", "dependency_scan"],
    },
    "archive-inspector": {
        "description": "Safe ZIP/tar inventory, checksums, duplicates, comparison and Zip-Slip-aware extraction.",
        "capabilities": {"required": [], "optional": ["7z"], "runtime": []},
        "operations": ["inspect", "compare", "extract"],
    },
    "data-profiler": {
        "description": "CSV, TSV, XLSX, JSONL and optional Parquet data quality/statistical profiling.",
        "capabilities": {"required": [], "optional": ["openpyxl", "pyarrow"], "runtime": []},
        "operations": ["profile", "quality", "correlation", "leakage_suspicion"],
    },
    "document-batch-processor": {
        "description": "Office-file inventory, classification, rename/move planning, hashing, deduplication and built-in Skill delegation.",
        "capabilities": {"required": [], "optional": [], "runtime": []},
        "operations": ["inventory", "classify", "plan", "copy", "move", "index"],
    },
    "release-notes": {
        "description": "Conventional-Commit-aware release notes, migration, risk, rollback and test summary generation.",
        "capabilities": {"required": [], "optional": ["git"], "runtime": []},
        "operations": ["generate", "changelog", "risk", "rollback"],
    },
    "web-research-report": {
        "description": "Browser-independent research methodology: source quality, freshness, cross-validation, conflicts and citations.",
        "capabilities": {"required": [], "optional": ["browser_builtin"], "runtime": []},
        "operations": ["plan", "synthesize", "cross_validate", "report"],
    },
}


RUNNER = '''"""Self-contained QwenPaw Skill CLI entry."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

SKILL_NAME = {skill_name!r}

try:
    skill_root = Path(__file__).resolve().parents[1]
    runtime_init = skill_root / "runtime" / "__init__.py"
    if not runtime_init.is_file():
        raise ImportError
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "runtime", runtime_init, submodule_search_locations=[str(runtime_init.parent)]
    )
    if spec is None or spec.loader is None:
        raise ImportError
    runtime_module = importlib.util.module_from_spec(spec)
    sys.modules["runtime"] = runtime_module
    spec.loader.exec_module(runtime_module)
    execute_skill = runtime_module.execute_skill
except ImportError:
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from core.productivity_skills import execute_skill


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{{SKILL_NAME}} structured executor")
    parser.add_argument("--request", help="inline JSON request")
    parser.add_argument("--request-file", help="UTF-8 JSON request file")
    args = parser.parse_args()
    if args.request_file:
        request = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
    elif args.request:
        request = json.loads(args.request)
    else:
        request = json.load(sys.stdin)
    response = execute_skill(SKILL_NAME, request)
    print(json.dumps(response, ensure_ascii=False, indent=2, default=str))
    return 0 if response["status"] in {{"SUCCESS", "PARTIAL_SUCCESS"}} else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _skill_doc(name: str, metadata: dict) -> str:
    operations = "\n".join(f"- `{item}`" for item in metadata["operations"])
    runtime = ", ".join(metadata["capabilities"]["runtime"]) or "none"
    return f'''---
name: {name}
description: "{metadata['description']}"
---

# {name}

Use this Skill only for its incremental capability. Do not replace QwenPaw
built-in PDF, DOCX, XLSX, PPTX, Browser, Channel, plan or multi-agent Skills.

## Operations

{operations}

## Execution

Run from this Skill directory:

```bash
python scripts/run.py --request '{{"operation":"{metadata['operations'][0]}"}}'
```

Every response is JSON and uses one of `SUCCESS`, `PARTIAL_SUCCESS`,
`DEPENDENCY_MISSING`, `MODEL_RUNTIME_REQUIRED`, `UNSUPPORTED`, `INVALID_INPUT`
or `FAILED`. A file-producing success includes Artifact metadata. Source files
are never overwritten. Optional model Runtime capabilities: {runtime}.

Never claim an unavailable dependency/model operation succeeded. Never put
credentials, model weights, caches or machine-specific paths into this Skill.
'''


def generate(repository_root: Path, *, force: bool = False) -> None:
    skills_root = repository_root / "skills"
    for name, metadata in SKILLS.items():
        root = skills_root / name
        if root.exists() and not force:
            raise FileExistsError(f"Skill already exists: {root}")
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "tests").mkdir(parents=True, exist_ok=True)
        (root / "schemas").mkdir(parents=True, exist_ok=True)
        (root / "SKILL.md").write_text(_skill_doc(name, metadata), encoding="utf-8")
        (root / "README.md").write_text(
            f"# {name}\n\n{metadata['description']}\n\n"
            "The source launcher uses the repository's canonical productivity runtime. "
            "The release builder vendors the required runtime into each standalone ZIP.\n",
            encoding="utf-8",
        )
        descriptor = {
            "schema_version": "qwenpaw-productivity-skill.v1",
            "name": name,
            "version": "1.0.0",
            "description": metadata["description"],
            "entrypoint": "scripts/run.py",
            "handler": name,
            "operations": metadata["operations"],
            "capabilities": metadata["capabilities"],
            "statuses": ["SUCCESS", "PARTIAL_SUCCESS", "DEPENDENCY_MISSING", "MODEL_RUNTIME_REQUIRED", "UNSUPPORTED", "INVALID_INPUT", "FAILED"],
            "artifact_contract": {"required_metadata": ["operation", "source", "output", "mime_type", "size", "checksum"], "overwrite_source": False},
        }
        (root / "skill.yaml").write_text(json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "scripts" / "run.py").write_text(RUNNER.format(skill_name=name), encoding="utf-8")
        (root / "tests" / "README.md").write_text(
            "# Tests\n\nUnit, isolated-package, Artifact, dependency-missing and invalid-input "
            "coverage is maintained under `tests/skills/` in the development repository.\n",
            encoding="utf-8",
        )
        request_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": {"operation": {"type": "string"}, "input": {"type": "string"}, "output_dir": {"type": "string"}}, "additionalProperties": True}
        result_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["status", "message", "data", "artifacts", "capabilities"], "properties": {"status": {"enum": descriptor["statuses"]}, "message": {"type": "string"}, "data": {"type": "object"}, "artifacts": {"type": "array"}, "error": {"type": ["object", "null"]}, "capabilities": {"type": "object"}}}
        (root / "schemas" / "request.schema.json").write_text(json.dumps(request_schema, indent=2) + "\n", encoding="utf-8")
        (root / "schemas" / "result.schema.json").write_text(json.dumps(result_schema, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(Path(args.repository_root).resolve(), force=args.force)
    print(json.dumps({"generated": list(SKILLS), "count": len(SKILLS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
