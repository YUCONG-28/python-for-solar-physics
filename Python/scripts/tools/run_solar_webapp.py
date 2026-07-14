"""Run the local Solar Physics Workbench web GUI."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from solar_toolkit.webapp.cli import main as webapp_main

    return webapp_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
