"""Recommended entrypoint for the SDO/AIA EUV FITS processor."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.aia.cli import main  # noqa: E402

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
