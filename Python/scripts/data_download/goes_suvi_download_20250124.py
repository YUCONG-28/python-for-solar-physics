#!/usr/bin/env python3
"""Download GOES-16/18 SUVI L2 composites for 2025-01-24 04:00-05:00 UT."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from solar_toolkit.net.downloads import download_url, fetch_text
from solar_toolkit.net.links import collect_links
from solar_toolkit.net.suvi import (
    DEFAULT_BASE_URL,
    DEFAULT_CHANNELS,
    DEFAULT_SATELLITES,
    download_goes_suvi,
    is_suvi_file_in_window,
)

BASE = DEFAULT_BASE_URL
SATELLITES = DEFAULT_SATELLITES
CHANNELS = DEFAULT_CHANNELS
DATE_PATH = "2025/01/24"
DATE_STAMP = "20250124"
START_MIN = "040000"
START_MAX = "045959"
OUT_ROOT = Path(os.getenv("SUVI_DATA_ROOT", "data/raw/suvi"))


def list_links(url: str) -> list[str]:
    """Compatibility wrapper returning links from an archive listing."""

    return collect_links(fetch_text(url, timeout=60))


def wanted_file(name: str, satellite: str, channel: str) -> bool:
    """Compatibility wrapper for the historical fixed-date selector."""

    return is_suvi_file_in_window(
        name,
        satellite=satellite,
        channel=channel,
        date_stamp=DATE_STAMP,
        start_hms=START_MIN,
        end_hms=START_MAX,
    )


def download(url: str, dest: Path) -> bool:
    """Compatibility wrapper returning whether a file was newly downloaded."""

    return (
        download_url(
            url,
            dest,
            timeout=120,
            chunk_size=1024 * 1024,
            redownload_empty=True,
        ).status
        == "downloaded"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(OUT_ROOT))
    parser.add_argument("--base-url", default=BASE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    download_goes_suvi(
        output_root=args.output_root,
        date_path=DATE_PATH,
        date_stamp=DATE_STAMP,
        start_hms=START_MIN,
        end_hms=START_MAX,
        base_url=args.base_url,
        satellites=SATELLITES,
        channels=CHANNELS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
