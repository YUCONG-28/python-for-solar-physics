"""Run the packaged HMI magnetogram workflow on local FITS files.

The historical filename is retained for link compatibility.  The recipe is
import-safe and delegates all file selection, WCS alignment, and plotting to
the public :mod:`solar_toolkit.hmi.magnetogram` API.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from solar_toolkit.hmi.magnetogram import run_magnetogram_workflow

REQUIRES_LOCAL_DATA = True


def build_parser() -> argparse.ArgumentParser:
    """Build the real-data recipe parser."""

    parser = argparse.ArgumentParser(
        description="Render aligned HMI magnetograms from a local FITS directory."
    )
    parser.add_argument("input_dir", help="Directory containing HMI FITS files.")
    parser.add_argument("output_dir", help="Directory for generated PNG files.")
    parser.add_argument("--frame-count", type=int, default=1)
    parser.add_argument("--show", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged workflow and return a process status code."""

    args = build_parser().parse_args(argv)
    outputs = run_magnetogram_workflow(
        args.input_dir,
        args.output_dir,
        frame_count=args.frame_count,
        show_plot=args.show,
    )
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
