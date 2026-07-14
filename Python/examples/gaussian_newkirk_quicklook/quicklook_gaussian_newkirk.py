"""Generate Gaussian/Newkirk quicklooks from a local diagnostics CSV."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from solar_toolkit.radio.quicklook import run_gaussian_newkirk_quicklook

DEFAULT_CONFIG_NAME = "radio_20250124_config"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "quicklook_outputs"
REQUIRES_LOCAL_DATA = True


def run_quicklook(
    *,
    gaussian_csv: str | Path | None = None,
    config_name: str = DEFAULT_CONFIG_NAME,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the public quicklook API with this recipe's output default."""

    return run_gaussian_newkirk_quicklook(
        gaussian_csv=gaussian_csv,
        config_name=config_name,
        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the real-data recipe parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate Gaussian center trajectory and Gaussian/Newkirk height "
            "quicklook plots from a diagnostics CSV."
        )
    )
    parser.add_argument(
        "--gaussian-csv",
        help="Path to radio_gaussian_fit_diagnostics.csv or a compatible CSV.",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated quicklook CSV and PNG outputs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the real-data recipe and return a process status code."""

    args = build_parser().parse_args(argv)
    outputs = run_quicklook(
        gaussian_csv=args.gaussian_csv,
        config_name=args.config,
        output_dir=args.output_dir,
    )
    summary = outputs["summary"]
    print(f"input_csv: {outputs['input_csv']}")
    print(f"gaussian_rows: {summary['gaussian_rows']}")
    print(f"valid_trajectory_rows: {summary['valid_trajectory_rows']}")
    for label, path in outputs.items():
        if label != "summary":
            print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
