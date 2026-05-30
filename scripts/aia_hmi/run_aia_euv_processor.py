"""Recommended entrypoint for the SDO/AIA EUV FITS processor."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.aia_hmi.core.aia_cli import main  # noqa: E402

__all__ = ["main"]


if __name__ == "__main__":
    main()
