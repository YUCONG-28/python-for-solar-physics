#!/usr/bin/env python3
"""Compatibility CLI for SOHO/LASCO adjacent running-difference plots."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from solar_toolkit.cme import extract_lasco_timestamp, scan_lasco_files
from solar_toolkit.cme.lasco import render_lasco_running_differences
from solar_toolkit.path_config import load_script_config

DEFAULT_INPUT_DIR = "data/lasco"
DEFAULT_OUTPUT_DIR = "outputs/lasco/difference"


def extract_timestamp_from_filename(filename: str) -> dt.datetime:
    """Compatibility wrapper returning ``datetime.min`` for unknown names."""

    try:
        return extract_lasco_timestamp(filename)
    except ValueError:
        return dt.datetime.min


def get_jp2_files(input_dir: str | Path, recursive: bool = True) -> list[Path]:
    """Compatibility wrapper for the canonical LASCO scanner."""

    root = Path(input_dir)
    if not root.is_dir():
        return []
    return [
        path
        for path in scan_lasco_files(root, recursive=recursive)
        if path.suffix.casefold() == ".jp2"
    ]


def setup_chinese_font() -> None:
    """Retain the historical plotting-font helper without import side effects."""

    import matplotlib.pyplot as plt

    plt.rcParams["axes.unicode_minus"] = False
    try:
        plt.rcParams["font.family"] = ["SimHei"]
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--show-plot", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument(
        "--recursive", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--vmin", type=float, default=-49)
    parser.add_argument("--vmax", type=float, default=49)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_script_config(
        "soho_lasco_running_difference",
        {
            "input_dir": DEFAULT_INPUT_DIR,
            "output_dir": DEFAULT_OUTPUT_DIR,
            "show_plot": False,
        },
    )
    render_lasco_running_differences(
        args.input_dir or config["input_dir"],
        args.output_dir or config["output_dir"],
        show_plot=(
            bool(config.get("show_plot", False))
            if args.show_plot is None
            else args.show_plot
        ),
        recursive=args.recursive,
        vmin=args.vmin,
        vmax=args.vmax,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
