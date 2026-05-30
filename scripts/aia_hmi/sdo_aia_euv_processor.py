"""Compatibility entrypoint for the SDO/AIA EUV FITS processor.

The implementation is organized under ``scripts.aia_hmi.core``. This file
keeps the historical command and import path working.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.aia_hmi.core.aia_cli import (  # noqa: E402
    build_parser,
    config_from_args,
    main,
)
from scripts.aia_hmi.core.aia_config import (  # noqa: E402
    AIA_CONFIG,
    DIFF_CONFIG,
    AIAConfig,
)
from scripts.aia_hmi.core.aia_processor import process_aia_fits  # noqa: E402

__all__ = [
    "AIA_CONFIG",
    "DIFF_CONFIG",
    "AIAConfig",
    "build_parser",
    "config_from_args",
    "process_aia_fits",
    "main",
]


if __name__ == "__main__":
    main()
