"""Compatibility entrypoint for RR+LL percentile-comparison previews."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.radio.rrll_percentile_preview_comparison import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
