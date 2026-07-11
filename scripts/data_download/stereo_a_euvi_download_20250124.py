#!/usr/bin/env python3
"""Download the selected 2025-01-24 STEREO-A/EUVI interval."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from solar_toolkit.net.downloads import download_url
from solar_toolkit.net.stereo import DEFAULT_BASE_URL, download_stereo_euvi

BASE_URL = DEFAULT_BASE_URL
OUT_DIR = Path(os.getenv("STEREO_EUVI_DATA_DIR", "data/raw/stereo/euvi/20250124"))
START = "2025-01-24 04:00"
END = "2025-01-24 05:00"


def download(url: str, dest: Path) -> str:
    """Compatibility wrapper retaining the historical status strings."""

    result = download_url(
        url,
        dest,
        timeout=180,
        chunk_size=1024 * 1024,
        redownload_empty=True,
    )
    return "downloaded" if result.status == "downloaded" else "exists"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--base-url", default=BASE_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return download_stereo_euvi(
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
        base_url=args.base_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())
