"""Generate isolated Gaussian/Newkirk quicklook plots from diagnostics CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_CONFIG_NAME = "radio_20250124_config"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "quicklook_outputs"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_repo_root_on_path() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def run_quicklook(
    *,
    gaussian_csv: str | Path | None = None,
    config_name: str = DEFAULT_CONFIG_NAME,
    output_dir: str | Path | None = None,
) -> dict:
    """Run the core quicklook helper with the example's default output path."""
    _ensure_repo_root_on_path()
    from solar_toolkit.radio.quicklook import run_gaussian_newkirk_quicklook

    return run_gaussian_newkirk_quicklook(
        gaussian_csv=gaussian_csv,
        config_name=config_name,
        output_dir=output_dir or DEFAULT_OUTPUT_DIR,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = _parse_args(argv)
    outputs = run_quicklook(
        gaussian_csv=args.gaussian_csv,
        config_name=args.config,
        output_dir=args.output_dir,
    )
    summary = outputs["summary"]
    print("[Gaussian/Newkirk Quicklook] input:")
    print(f"  gaussian_csv: {outputs['input_csv']}")
    print(f"  gaussian_rows: {summary['gaussian_rows']}")
    print(f"  valid_trajectory_rows: {summary['valid_trajectory_rows']}")
    print(
        "  valid_center_x_arcsec: "
        f"{summary['valid_center_x_arcsec']['min']}.."
        f"{summary['valid_center_x_arcsec']['max']}"
    )
    print(
        "  valid_center_y_arcsec: "
        f"{summary['valid_center_y_arcsec']['min']}.."
        f"{summary['valid_center_y_arcsec']['max']}"
    )
    print(
        "  projected_height_valid/invalid: "
        f"{summary['projected_height_valid_count']}/"
        f"{summary['projected_height_invalid_count']}"
    )
    if summary["valid_trajectory_rows"] < 50:
        print(
            "  warning: small valid trajectory sample; this may be a retune "
            "verification CSV rather than a full-event diagnostics table."
        )
    print("[Gaussian/Newkirk Quicklook] outputs:")
    for label, path in outputs.items():
        if label == "summary":
            continue
        print(f"  {label}: {path}")
    return outputs


if __name__ == "__main__":
    main()
