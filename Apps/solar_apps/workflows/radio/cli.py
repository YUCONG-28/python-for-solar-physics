"""Local radio command adapter."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="solar-apps workflow radio",
        description="Run local radio-analysis workflows.",
        epilog=(
            "Pass a workflow name and its arguments after this wrapper. "
            "Use '<workflow> --help' for workflow-specific help."
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        build_parser().print_help()
        return 0
    from .dispatcher import main as dispatcher_main

    result = dispatcher_main(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
