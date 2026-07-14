"""Command-line entry point for HMI magnetogram plotting."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from solar_toolkit.hmi.magnetogram import (
    DEFAULT_DATA_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_ROI_BOUNDS,
    run_magnetogram_workflow,
)
from solar_toolkit.path_config import load_script_config

_DEFAULT_CONFIG = {
    "data_dir": str(DEFAULT_DATA_DIR),
    "output_dir": str(DEFAULT_OUTPUT_DIR),
    "roi_bounds": DEFAULT_ROI_BOUNDS,
    "frame_count": 1,
    "dpi": 200,
    "show_plot": False,
}


def _build_parser(config: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reproject and render local SDO/HMI magnetogram FITS files."
    )
    parser.add_argument("--data-dir", default=config["data_dir"])
    parser.add_argument("--output-dir", default=config["output_dir"])
    parser.add_argument(
        "--roi-bounds",
        nargs=4,
        type=float,
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
        default=config.get("roi_bounds", DEFAULT_ROI_BOUNDS),
    )
    parser.add_argument(
        "--frame-count",
        type=int,
        default=int(config.get("frame_count", 1)),
    )
    parser.add_argument("--dpi", type=int, default=int(config.get("dpi", 200)))
    parser.add_argument(
        "--show-plot",
        action=argparse.BooleanOptionalAction,
        default=bool(config.get("show_plot", False)),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the configured HMI magnetogram workflow."""

    config = load_script_config("sdo_hmi_magnetogram_plot", _DEFAULT_CONFIG)
    args = _build_parser(config).parse_args(argv)
    output_paths = run_magnetogram_workflow(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        roi_bounds=tuple(args.roi_bounds),
        frame_count=args.frame_count,
        show_plot=args.show_plot,
        dpi=args.dpi,
    )
    print(f"Generated {len(output_paths)} HMI magnetogram image(s)")
    return 0


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
