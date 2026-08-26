"""Self-contained QwenPaw Skill CLI entry."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

SKILL_NAME = 'sql-diagnostics'

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
    parser = argparse.ArgumentParser(description=f"{SKILL_NAME} structured executor")
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
    return 0 if response["status"] in {"SUCCESS", "PARTIAL_SUCCESS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
