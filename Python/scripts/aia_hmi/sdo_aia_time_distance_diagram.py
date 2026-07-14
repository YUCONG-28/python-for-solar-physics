"""Compatibility launcher for the archived SunPy time-distance recipe."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

__all__ = ["build_parser", "main"]

_RECIPE = (
    Path(__file__).resolve().parents[2]
    / "examples"
    / "history"
    / "aia_hmi"
    / "time_distance_diagram_legacy.py"
)


def build_parser() -> argparse.ArgumentParser:
    """Build a help-only parser for the archived network recipe."""
    return argparse.ArgumentParser(
        description="Run the archived SunPy AIA time-distance recipe."
    )


def main(argv: list[str] | None = None) -> int:
    """Execute the archived network-backed recipe in a source checkout."""
    build_parser().parse_args(argv)
    previous = sys.argv
    sys.argv = [str(_RECIPE), *(argv or [])]
    try:
        runpy.run_path(str(_RECIPE), run_name="__main__")
    finally:
        sys.argv = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
