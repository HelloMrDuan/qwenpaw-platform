"""Generate a deterministic offline AgentScope Extension install report."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable, Sequence


SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from core.deployment import (  # noqa: E402
    AgentScopeDeploymentAdapter,
    AgentScopeDeploymentBridgeError,
)


INSTALL_REPORT_SCHEMA_VERSION = "qwenpaw-agentscope-install-report.v1"
RUNTIME_DISCOVERY_STATUS = "NOT_EXECUTED"


class InstallReportError(ValueError):
    """Raised when an offline install report cannot be generated safely."""


def build_install_report(
    package_paths: Iterable[str | Path],
    workspace_root: str | Path,
    *,
    available_secrets: Iterable[str] = (),
    adapter: AgentScopeDeploymentAdapter | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe report without changing the Workspace or filesystem."""

    packages = tuple(Path(path).resolve() for path in package_paths)
    if not packages:
        raise InstallReportError("at least one Extension package is required")
    secret_names = tuple(available_secrets)
    deployment_adapter = adapter or AgentScopeDeploymentAdapter()
    plans = [
        deployment_adapter.create_install_plan(
            package,
            workspace_root,
            available_secrets=secret_names,
        )
        for package in packages
    ]
    names = [plan.package.name for plan in plans]
    if len(set(names)) != len(names):
        raise InstallReportError(
            "install report cannot contain duplicate Extension names"
        )
    records = [
        {
            "extension": plan.package.name,
            "type": plan.package.type.value,
            "version": plan.package.version,
            "target_path": str(plan.mapping.target_directory),
            "required_secrets": list(plan.secrets.required),
            "missing_secrets": list(plan.secrets.missing),
            "ready": plan.ready,
            "plan_id": plan.plan_id,
        }
        for plan in sorted(plans, key=lambda item: item.package.name)
    ]
    return {
        "schema_version": INSTALL_REPORT_SCHEMA_VERSION,
        "workspace_root": str(Path(workspace_root).resolve()),
        "runtime_discovery": RUNTIME_DISCOVERY_STATUS,
        "all_ready": all(record["ready"] for record in records),
        "extensions": records,
    }


def generate_install_report(
    package_paths: Iterable[str | Path],
    workspace_root: str | Path,
    output_path: str | Path = "install-report.json",
    *,
    available_secrets: Iterable[str] = (),
    adapter: AgentScopeDeploymentAdapter | None = None,
) -> Path:
    """Atomically write install-report.json and return its resolved path."""

    report = build_install_report(
        package_paths,
        workspace_root,
        available_secrets=available_secrets,
        adapter=adapter,
    )
    output = Path(output_path).resolve()
    workspace = Path(workspace_root).resolve()
    if output.suffix.lower() != ".json":
        raise InstallReportError("install report output must use a .json suffix")
    if output.exists() and output.is_dir():
        raise InstallReportError("install report output cannot be a directory")
    if output == workspace or output.is_relative_to(workspace):
        raise InstallReportError(
            "install report output must remain outside the target Workspace"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an offline AgentScope Extension install report."
    )
    parser.add_argument(
        "--package",
        action="append",
        required=True,
        dest="packages",
        help="Extension ZIP path; repeat for multiple packages.",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        help="Logical AgentScope Workspace root; it is not modified.",
    )
    parser.add_argument(
        "--output",
        default="install-report.json",
        help="Report path (default: install-report.json).",
    )
    parser.add_argument(
        "--available-secret",
        action="append",
        default=[],
        dest="available_secrets",
        help="Available secret name only; repeat as needed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = generate_install_report(
            args.packages,
            args.workspace,
            args.output,
            available_secrets=args.available_secrets,
        )
    except (AgentScopeDeploymentBridgeError, InstallReportError, OSError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {"ok": True, "report": str(output)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
