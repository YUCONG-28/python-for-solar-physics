#!/usr/bin/env python3
"""Compatibility CLI for downloading an SOHO/LASCO C2 JP2 sequence."""

from __future__ import annotations

import argparse
import datetime as dt

from solar_toolkit.cme.lasco import download_lasco_jp2_sequence
from solar_toolkit.path_config import load_script_config

DEFAULT_START = "2024-08-08T19:00:00"
DEFAULT_END = "2024-08-08T23:00:00"
DEFAULT_INTERVAL_SECONDS = 720
DEFAULT_SAVE_DIR = "data/lasco"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=DEFAULT_START, help="Inclusive ISO time.")
    parser.add_argument("--end", default=DEFAULT_END, help="Inclusive ISO time.")
    parser.add_argument(
        "--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS
    )
    parser.add_argument("--save-dir", help="Override configured output directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be positive")
    config = load_script_config(
        "soho_lasco_data_download", {"save_dir": DEFAULT_SAVE_DIR}
    )
    attempted, saved = download_lasco_jp2_sequence(
        start_time=dt.datetime.fromisoformat(args.start),
        end_time=dt.datetime.fromisoformat(args.end),
        interval=dt.timedelta(seconds=args.interval_seconds),
        output_dir=args.save_dir or config["save_dir"],
    )
    return 0 if attempted == saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
