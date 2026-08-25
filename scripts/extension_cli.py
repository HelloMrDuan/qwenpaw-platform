"""Command-line interface for the local Extension lifecycle simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

SCRIPT_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPOSITORY_ROOT))

from core.extensions.lifecycle import (  # noqa: E402
    ExtensionLifecycleError,
    ExtensionLifecycleManager,
)
from scripts.deploy_extension import DEFAULT_DEPLOYMENT_ROOT  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extension",
        description="Manage the local, non-executable Extension lifecycle simulation.",
    )
    parser.add_argument(
        "--target",
        default=str(DEFAULT_DEPLOYMENT_ROOT),
        help="Deployment root (default: workspace/extensions).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="List locally installed Extensions.")

    install = commands.add_parser("install", help="Verify and install an Extension ZIP.")
    install.add_argument("package", help="Extension ZIP path.")
    install.add_argument("--sha256", help="Expected SHA256 (sidecar used by default).")

    enable = commands.add_parser("enable", help="Enable an installed Extension.")
    enable.add_argument("name", help="Extension name.")

    disable = commands.add_parser("disable", help="Disable an Extension locally.")
    disable.add_argument("name", help="Extension name.")

    health = commands.add_parser("health", help="Check local deployment integrity/state.")
    health.add_argument("name", help="Extension name.")

    rollback = commands.add_parser("rollback", help="Activate an installed prior version.")
    rollback.add_argument("name", help="Extension name.")
    rollback.add_argument("--version", help="Target version (previous version by default).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = ExtensionLifecycleManager(args.target)
    try:
        if args.command == "list":
            output = [record.to_dict() for record in manager.list()]
        elif args.command == "install":
            output = manager.install(
                args.package, expected_sha256=args.sha256
            ).to_dict()
        elif args.command == "enable":
            output = manager.enable(args.name).to_dict()
        elif args.command == "disable":
            output = manager.disable(args.name).to_dict()
        elif args.command == "health":
            output = manager.health(args.name).to_dict()
        elif args.command == "rollback":
            output = manager.rollback(args.name, version=args.version).to_dict()
        else:  # pragma: no cover - argparse enforces the command set.
            raise ExtensionLifecycleError(f"unsupported command: {args.command}")
    except ExtensionLifecycleError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
