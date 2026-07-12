#!/usr/bin/env python3
"""Compatibility CLI for plotting SOHO/LASCO JP2 images."""

from __future__ import annotations

import argparse

from solar_toolkit.cme.lasco import plot_lasco_images
from solar_toolkit.path_config import load_script_config

DEFAULT_INPUT_DIR = "data/lasco"
DEFAULT_OUTPUT_DIR = "outputs/lasco/plots"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir")
    parser.add_argument("--output-dir")
    parser.add_argument(
        "--show-plot", action=argparse.BooleanOptionalAction, default=None
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_script_config(
        "soho_lasco_image_plot",
        {
            "input_dir": DEFAULT_INPUT_DIR,
            "output_dir": DEFAULT_OUTPUT_DIR,
            "show_plot": False,
        },
    )
    plot_lasco_images(
        args.input_dir or config["input_dir"],
        args.output_dir or config["output_dir"],
        show_plot=(
            bool(config.get("show_plot", False))
            if args.show_plot is None
            else args.show_plot
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
