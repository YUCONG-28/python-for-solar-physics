#!/usr/bin/env python3
"""Query and optionally download Solar Orbiter/EUI FITS files from SOAR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solar_toolkit.net.soar import (
    DEFAULT_DATA_URL,
    DEFAULT_TAP_URL,
    download_eui_rows,
    print_eui_summary,
    query_eui,
)
from solar_toolkit.net.soar import (
    unique_rows as _unique_rows,
)

START = "2025-01-24 04:00:00"
END = "2025-01-24 05:00:00"
TAP_URL = DEFAULT_TAP_URL
DATA_URL = DEFAULT_DATA_URL
unique_rows = _unique_rows


def print_summary(rows: list[dict]) -> None:
    """Compatibility wrapper for the canonical SOAR summary."""

    print_eui_summary(rows)


def download(rows: list[dict], outdir: Path, descriptor: str | None) -> None:
    """Compatibility wrapper for the canonical SOAR downloader."""

    download_eui_rows(rows, outdir, descriptor=descriptor, data_url=DATA_URL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    parser.add_argument("--outdir", default="data/raw/solo/eui/20250124")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--descriptor", help="Download only one descriptor.")
    parser.add_argument("--tap-url", default=TAP_URL)
    parser.add_argument("--data-url", default=DATA_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outdir = Path(args.outdir)
    rows = query_eui(args.start, args.end, tap_url=args.tap_url)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = outdir / "soar_eui_20250124_0400_0500_metadata.json"
    manifest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print_eui_summary(rows)
    print(f"saved manifest: {manifest}")
    if args.download:
        download_eui_rows(
            rows,
            outdir,
            descriptor=args.descriptor,
            data_url=args.data_url,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
