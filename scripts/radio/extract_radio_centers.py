"""Thin CLI for threshold radio-source center extraction."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.radio.centers import build_parser
from solar_toolkit.radio.centers import main as _centers_main

__all__ = ["build_parser", "main"]


def main(argv: list[str] | None = None):
    """Run the reusable radio-center extraction CLI."""

    return _centers_main(argv)


if __name__ == "__main__":
    main()
