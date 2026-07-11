"""Inspect selected metadata from one or more local FITS files.

The example is import-safe and reads data only after :func:`main` is called.
FITS access is delegated to the public :mod:`solar_toolkit.io` API.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from solar_toolkit.io import read_fits_data_header

REQUIRES_LOCAL_DATA = True
DEFAULT_KEYS = ("DATE-OBS", "INSTRUME", "WAVELNTH", "NAXIS1", "NAXIS2")


def build_parser() -> argparse.ArgumentParser:
    """Build the real-data recipe parser."""

    parser = argparse.ArgumentParser(description="Inspect local FITS headers.")
    parser.add_argument("paths", nargs="+", help="One or more FITS files.")
    parser.add_argument("--hdu", type=int, default=0, help="HDU index to inspect.")
    return parser


def inspect_headers(
    paths: Sequence[str | Path],
    *,
    hdu_index: int = 0,
) -> list[tuple[Path, tuple[int, ...], dict[str, object]]]:
    """Return array shapes and a compact header selection for ``paths``."""

    rows = []
    for value in paths:
        path = Path(value)
        data, header = read_fits_data_header(path, hdu_index=hdu_index)
        metadata = {key: header.get(key) for key in DEFAULT_KEYS}
        shape = () if data is None else tuple(data.shape)
        rows.append((path, shape, metadata))
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    """Print compact FITS metadata and return a process status code."""

    args = build_parser().parse_args(argv)
    for path, shape, metadata in inspect_headers(args.paths, hdu_index=args.hdu):
        print(f"{path}: shape={shape}")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
