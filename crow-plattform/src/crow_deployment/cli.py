from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .modules import build_module_install_plan, find_repository_root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crow-install-modules",
        description="Install every first-party Crow module declared in the module layout manifest.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Crow Platform repository root. Defaults to discovery from the current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the dependency-ordered module plan without invoking pip.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.root.resolve() if args.root is not None else find_repository_root()
    plan = build_module_install_plan(root)

    for module_id, repository_root in zip(plan.module_ids, plan.repository_roots, strict=True):
        print(f"{module_id}: {repository_root}")
        if not args.dry_run:
            subprocess.run(
                (sys.executable, "-m", "pip", "install", "-e", str(repository_root)),
                check=True,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
