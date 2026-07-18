"""Export a static Plotly HTML radio-source trajectory view."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from solar_toolkit.aia.background import load_nearest_background, scan_aia_folder
from solar_apps.workflows.visualization.radio_source_trajectory import (
    build_trajectory_figure,
    export_trajectory_html,
)

from solar_toolkit.radio.trajectory import (
    FRAME_MODE_TAIL,
    filter_centers,
    frame_times,
    load_centers_table,
    select_visible_centers,
)

__all__ = ["build_parser", "main", "run_trajectory_export"]


def build_parser() -> argparse.ArgumentParser:
    """Build parser for static trajectory HTML export."""

    parser = argparse.ArgumentParser(
        prog="Apps/run.ps1 workflow radio trajectory",
        description="Export radio-source trajectory centers to a Plotly HTML file.",
    )
    parser.add_argument("--centers", required=True, help="Input center CSV/XLSX table.")
    parser.add_argument("--out", required=True, help="Output HTML path.")
    parser.add_argument("--frame-time", help="Frame time to display, ISO-like string.")
    parser.add_argument(
        "--frame-index",
        type=int,
        default=-1,
        help="Frame index when --frame-time is omitted; default is the last frame.",
    )
    parser.add_argument(
        "--mode", default=FRAME_MODE_TAIL, help="current, tail, or all."
    )
    parser.add_argument(
        "--tail-n", type=int, default=5, help="Tail length for tail mode."
    )
    parser.add_argument("--freqs", help="Comma-separated frequencies in MHz.")
    parser.add_argument("--polarizations", help="Comma-separated polarizations.")
    parser.add_argument("--center-methods", help="Comma-separated center methods.")
    parser.add_argument("--no-lines", action="store_true", help="Draw markers only.")
    parser.add_argument(
        "--compare-lr", action="store_true", help="Draw LCP-RCP segments."
    )
    parser.add_argument(
        "--compare-tolerance-sec",
        type=float,
        default=1.0,
        help="LCP/RCP nearest-time tolerance.",
    )
    parser.add_argument("--aia-dir", help="Optional AIA FITS folder for background.")
    parser.add_argument(
        "--aia-pattern", default="*.fits", help="AIA FITS glob pattern."
    )
    parser.add_argument(
        "--max-aia-dt-sec",
        type=float,
        default=3600.0,
        help="Maximum AIA/radio frame time difference.",
    )
    parser.add_argument("--aia-max-pixels", type=int, default=1024)
    parser.add_argument(
        "--aia-linear", action="store_true", help="Disable log10 AIA scaling."
    )
    parser.add_argument("--aia-wcs-mode", choices=["header", "sunpy"], default="header")
    return parser


def run_trajectory_export(
    centers_path: str | Path,
    output_path: str | Path,
    *,
    frame_time: str | None = None,
    frame_index: int = -1,
    mode: str = FRAME_MODE_TAIL,
    tail_n: int = 5,
    freqs: list[float] | None = None,
    polarizations: list[str] | None = None,
    center_methods: list[str] | None = None,
    draw_lines: bool = True,
    compare_lr: bool = False,
    compare_tolerance_sec: float = 1.0,
    aia_dir: str | Path | None = None,
    aia_pattern: str = "*.fits",
    max_aia_dt_sec: float = 3600.0,
    aia_max_pixels: int = 1024,
    aia_log_scale: bool = True,
    aia_wcs_mode: str = "header",
) -> Path:
    """Export one trajectory frame and return the generated HTML path."""

    centers = load_centers_table(centers_path)
    centers = filter_centers(
        centers,
        freqs=freqs,
        polarizations=polarizations,
        center_methods=center_methods,
    )
    if centers.empty:
        raise ValueError("No center rows remain after filtering.")
    selected_frame_time = _resolve_frame_time(
        centers,
        frame_time=frame_time,
        frame_index=frame_index,
    )
    visible = select_visible_centers(
        centers,
        selected_frame_time,
        mode=mode,
        tail_n=tail_n,
    )

    aia_background = None
    title_extra = ""
    if aia_dir:
        aia_table = scan_aia_folder(aia_dir, pattern=aia_pattern)
        aia_background, nearest = load_nearest_background(
            aia_table,
            selected_frame_time,
            max_dt_seconds=max_aia_dt_sec,
            max_pixels=aia_max_pixels,
            log_scale=aia_log_scale,
            wcs_mode=aia_wcs_mode,
        )
        if nearest.status == "matched":
            title_extra = f"AIA dt={nearest.delta_seconds:.1f}s"
        else:
            title_extra = f"AIA skipped: {nearest.status}"

    fig, _compare = build_trajectory_figure(
        visible,
        selected_frame_time,
        aia_background=aia_background,
        draw_lines=draw_lines,
        compare_lr=compare_lr,
        compare_tolerance_sec=compare_tolerance_sec,
        title_extra=title_extra,
    )
    return export_trajectory_html(fig, output_path)


def main(argv: list[str] | None = None) -> int:
    """Run the static trajectory export command."""

    args = build_parser().parse_args(argv)
    out = run_trajectory_export(
        args.centers,
        args.out,
        frame_time=args.frame_time,
        frame_index=args.frame_index,
        mode=args.mode,
        tail_n=args.tail_n,
        freqs=_parse_float_list(args.freqs),
        polarizations=_parse_str_list(args.polarizations),
        center_methods=_parse_str_list(args.center_methods),
        draw_lines=not args.no_lines,
        compare_lr=args.compare_lr,
        compare_tolerance_sec=args.compare_tolerance_sec,
        aia_dir=args.aia_dir,
        aia_pattern=args.aia_pattern,
        max_aia_dt_sec=args.max_aia_dt_sec,
        aia_max_pixels=args.aia_max_pixels,
        aia_log_scale=not args.aia_linear,
        aia_wcs_mode=args.aia_wcs_mode,
    )
    print(f"Trajectory HTML: {out}")
    return 0


def _parse_str_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_float_list(raw: str | None) -> list[float]:
    return [float(item) for item in _parse_str_list(raw)]


def _resolve_frame_time(
    centers: pd.DataFrame,
    *,
    frame_time: str | None,
    frame_index: int,
) -> pd.Timestamp:
    if frame_time:
        return pd.Timestamp(frame_time)
    times = frame_times(centers)
    if not times:
        raise ValueError("No valid frame times in center table.")
    index = int(frame_index)
    if index < 0:
        index = len(times) + index
    index = max(0, min(index, len(times) - 1))
    return pd.Timestamp(times[index])


if __name__ == "__main__":
    raise SystemExit(main())
