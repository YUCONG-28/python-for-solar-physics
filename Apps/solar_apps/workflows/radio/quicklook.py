"""Quicklook helpers for Gaussian-center and Newkirk-height diagnostics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from solar_toolkit.radio.config import (
    load_newkirk_height_comparison_config,
    load_radio_diagnostic_presentation_config,
    load_radio_output_config,
    load_radio_user_config,
)
from .configs import DEFAULT_CONFIG_NAME
from solar_toolkit.radio.frequency_priority_diagnostics import (
    plot_event_gaussian_newkirk_height_comparison,
)
from solar_toolkit.radio.height_comparison import (
    build_gaussian_newkirk_height_table,
)
from solar_toolkit.radio.io import truthy
from solar_toolkit.radio._image_naming import build_radio_image_filename

VALID_CENTERS_NAME = "radio_gaussian_valid_centers.csv"
HEIGHT_ROWS_NAME = "gaussian_newkirk_height_rows.csv"
HEIGHT_PLOT_NAME = "event_gaussian_newkirk_height_comparison.png"
TRAJECTORY_PLOT_NAME = "gaussian_center_trajectory.png"
DEFAULT_ANALYSIS_SUBDIR = "gaussian_spectrogram_overlay"

__all__ = [
    "build_parser",
    "build_quicklook_config",
    "build_quicklook_summary",
    "filter_valid_gaussian_centers",
    "plot_gaussian_center_trajectory",
    "resolve_gaussian_csv",
    "run_gaussian_newkirk_quicklook",
    "main",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the isolated Gaussian/Newkirk quicklook CLI parser."""

    parser = argparse.ArgumentParser(
        prog="solar-apps workflow radio quicklook",
        description="Generate Gaussian center and Newkirk quicklook products.",
    )
    parser.add_argument("--gaussian-csv")
    parser.add_argument("--config", default=DEFAULT_CONFIG_NAME)
    parser.add_argument("--output-dir", default="quicklook_outputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the quicklook workflow from command-line arguments."""

    args = build_parser().parse_args(argv)
    result = run_gaussian_newkirk_quicklook(
        gaussian_csv=args.gaussian_csv,
        config_name=args.config,
        output_dir=args.output_dir,
    )
    print(f"Quicklook input: {result['input_csv']}")
    print(f"Quicklook output: {Path(args.output_dir).resolve()}")
    return 0


def build_quicklook_config(config_name: str = DEFAULT_CONFIG_NAME) -> dict[str, Any]:
    """Merge the config sections needed for isolated quicklook products."""
    _user_config, newkirk_config = load_radio_user_config(config_name)
    height_config = load_newkirk_height_comparison_config(config_name)
    presentation_config = load_radio_diagnostic_presentation_config(config_name)

    config = dict(height_config)
    for key in (
        "comparison_frequency_mhz",
        "drift_source_type_map",
        "drift_time_tolerance_s",
        "drift_frequency_tolerance_mhz",
        "max_adaptive_frequency_tolerance_mhz",
        "min_adaptive_frequency_tolerance_mhz",
        "selected_newkirk_multiplier",
        "selected_newkirk_harmonic",
        "reference_newkirk_assumption",
        "reverse_frequency_axis",
    ):
        if key in presentation_config and config.get(key) in (None, ""):
            config[key] = presentation_config[key]
        elif key in presentation_config and key not in config:
            config[key] = presentation_config[key]

    if config.get("solar_radius_arcsec") is None:
        config["solar_radius_arcsec"] = float(
            newkirk_config.get("solar_radius_arcsec", 959.63)
        )
    return config


def resolve_gaussian_csv(
    *,
    gaussian_csv: str | Path | None,
    config_name: str = DEFAULT_CONFIG_NAME,
) -> Path:
    """Resolve a diagnostics CSV from an explicit path or event output config."""
    if gaussian_csv:
        return Path(gaussian_csv)

    output_config = load_radio_output_config(config_name)
    output_dir = Path(output_config.get("output_dir") or ".")
    analysis_subdir = str(
        output_config.get("analysis_subdir") or DEFAULT_ANALYSIS_SUBDIR
    ).strip()
    if not analysis_subdir or analysis_subdir.lower() == "auto":
        analysis_subdir = DEFAULT_ANALYSIS_SUBDIR
    csv_name = output_config.get("gaussian_diagnostics_csv") or VALID_CENTERS_NAME
    if csv_name == VALID_CENTERS_NAME:
        csv_name = "radio_gaussian_fit_diagnostics.csv"
    return output_dir / analysis_subdir / csv_name


def filter_valid_gaussian_centers(df: pd.DataFrame) -> pd.DataFrame:
    """Keep fitted centers that are marked usable for overlay and trajectory plots."""
    required = {"quality_flag", "overlay_valid", "trajectory_valid"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"Gaussian diagnostics missing required columns: {sorted(missing)}"
        )
    mask = (
        df["quality_flag"].astype(str).str.lower().eq("ok")
        & df["overlay_valid"].map(truthy)
        & df["trajectory_valid"].map(truthy)
    )
    return df.loc[mask].copy().reset_index(drop=True)


def plot_gaussian_center_trajectory(df: pd.DataFrame, path: str | Path) -> Path:
    """Save an x/y Gaussian-center trajectory plot colored by frequency."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 6), dpi=180)
    if not df.empty:
        freqs = pd.to_numeric(df.get("freq"), errors="coerce")
        sc = ax.scatter(
            pd.to_numeric(df["center_x_arcsec"], errors="coerce"),
            pd.to_numeric(df["center_y_arcsec"], errors="coerce"),
            c=freqs,
            cmap="viridis",
            s=28,
            edgecolors="black",
            linewidths=0.3,
        )
        fig.colorbar(sc, ax=ax, label="Frequency (MHz)")
    ax.set_xlabel("x (arcsec)")
    ax.set_ylabel("y (arcsec)")
    ax.set_title("Gaussian center trajectory")
    ax.grid(True, linestyle=":", alpha=0.35)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def build_quicklook_summary(
    gaussian_df: pd.DataFrame,
    valid_centers: pd.DataFrame,
    height_rows: pd.DataFrame,
) -> dict[str, Any]:
    """Summarize quicklook inputs and derived height rows."""
    unique_height = height_rows.drop_duplicates(
        subset=["time", "frequency_mhz", "gaussian_x_arcsec", "gaussian_y_arcsec"]
    )
    projected_valid = (
        unique_height["gaussian_projected_height_valid"].astype(bool)
        if "gaussian_projected_height_valid" in unique_height.columns
        else pd.Series(dtype=bool)
    )
    return {
        "gaussian_rows": int(len(gaussian_df)),
        "valid_trajectory_rows": int(len(valid_centers)),
        "frequency_counts": {
            str(freq): int(count)
            for freq, count in pd.to_numeric(gaussian_df.get("freq"), errors="coerce")
            .value_counts()
            .sort_index()
            .items()
        },
        "valid_frequency_counts": {
            str(freq): int(count)
            for freq, count in pd.to_numeric(valid_centers.get("freq"), errors="coerce")
            .value_counts()
            .sort_index()
            .items()
        },
        "valid_center_x_arcsec": _safe_range(valid_centers, "center_x_arcsec"),
        "valid_center_y_arcsec": _safe_range(valid_centers, "center_y_arcsec"),
        "projected_height_valid_count": int(projected_valid.sum()),
        "projected_height_invalid_count": int(
            len(projected_valid) - projected_valid.sum()
        ),
        "gaussian_height_rsun": _safe_range(unique_height, "gaussian_height_rsun"),
    }


def run_gaussian_newkirk_quicklook(
    *,
    gaussian_csv: str | Path | None = None,
    config_name: str = DEFAULT_CONFIG_NAME,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate isolated Gaussian/Newkirk quicklook CSV and PNG products."""
    gaussian_path = resolve_gaussian_csv(
        gaussian_csv=gaussian_csv,
        config_name=config_name,
    )
    if not gaussian_path.exists():
        raise FileNotFoundError(f"Gaussian diagnostics CSV not found: {gaussian_path}")

    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    gaussian_df = pd.read_csv(gaussian_path)
    config = build_quicklook_config(config_name)

    valid_centers = filter_valid_gaussian_centers(gaussian_df)
    valid_centers_path = resolved_output_dir / VALID_CENTERS_NAME
    valid_centers.to_csv(valid_centers_path, index=False)

    height_rows = build_gaussian_newkirk_height_table(gaussian_df, config)
    height_rows_path = resolved_output_dir / HEIGHT_ROWS_NAME
    height_rows.to_csv(height_rows_path, index=False)

    batch_generated_at = datetime.now(timezone.utc)
    height_plot_path = resolved_output_dir / build_radio_image_filename(
        height_rows,
        sequence=1,
        product="newkirk_height_comparison",
        generated_at=batch_generated_at,
    )
    height_result = plot_event_gaussian_newkirk_height_comparison(
        height_rows,
        height_plot_path,
        config,
    )
    if height_result.get("status") != "saved":
        raise RuntimeError(
            "Height comparison plot was not saved: "
            f"{height_result.get('reason', 'unknown')}"
        )

    trajectory_plot_path = plot_gaussian_center_trajectory(
        valid_centers,
        resolved_output_dir
        / build_radio_image_filename(
            valid_centers,
            sequence=2,
            product="source_trajectory",
            generated_at=batch_generated_at,
        ),
    )

    summary = build_quicklook_summary(gaussian_df, valid_centers, height_rows)
    return {
        "input_csv": str(gaussian_path),
        "valid_centers_csv": str(valid_centers_path),
        "height_rows_csv": str(height_rows_path),
        "height_plot": str(height_plot_path),
        "trajectory_plot": str(trajectory_plot_path),
        "summary": summary,
    }


def _safe_range(df: pd.DataFrame, column: str) -> dict[str, float | None]:
    if column not in df.columns or df.empty:
        return {"min": None, "max": None}
    values = pd.to_numeric(df[column], errors="coerce").dropna()
    if values.empty:
        return {"min": None, "max": None}
    return {"min": float(values.min()), "max": float(values.max())}


if __name__ == "__main__":
    raise SystemExit(main())
