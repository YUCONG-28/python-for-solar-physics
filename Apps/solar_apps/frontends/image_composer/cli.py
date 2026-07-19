"""Import-safe command adapter for the PySide6 image composer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Apps/run.ps1 frontend image-composer",
        description="Run the local PySide6 free image composer.",
        epilog="Additional arguments are forwarded to the application parser.",
    )
    parser.add_argument(
        "--project", metavar="PATH", help="Optional .fic.json project to open."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(argument in {"-h", "--help"} for argument in args):
        build_parser().print_help()
        return 0
    from .application import main as application_main

    return int(application_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
