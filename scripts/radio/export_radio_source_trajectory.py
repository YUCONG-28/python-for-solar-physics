"""Export a static Plotly HTML radio-source trajectory view."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from solar_toolkit.aia.background import load_nearest_background, scan_aia_folder
from solar_toolkit.radio.trajectory import (
    FRAME_MODE_TAIL,
    filter_centers,
    frame_times,
    load_centers_table,
    select_visible_centers,
)
from solar_toolkit.visualization.radio_source_trajectory import (
    build_trajectory_figure,
    export_trajectory_html,
)


def build_parser() -> argparse.ArgumentParser:
    """Build parser for static trajectory HTML export."""

    parser = argparse.ArgumentParser(
        description="Export radio-source trajectory centers to a Plotly HTML file."
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
    parser.add_argument("--mode", default=FRAME_MODE_TAIL, help="current, tail, or all.")
    parser.add_argument("--tail-n", type=int, default=5, help="Tail length for tail mode.")
    parser.add_argument("--freqs", help="Comma-separated frequencies in MHz.")
    parser.add_argument("--polarizations", help="Comma-separated polarizations.")
    parser.add_argument("--center-methods", help="Comma-separated center methods.")
    parser.add_argument("--no-lines", action="store_true", help="Draw markers only.")
    parser.add_argument("--compare-lr", action="store_true", help="Draw LCP-RCP segments.")
    parser.add_argument(
        "--compare-tolerance-sec",
        type=float,
        default=1.0,
        help="LCP/RCP nearest-time tolerance.",
    )
    parser.add_argument("--aia-dir", help="Optional AIA FITS folder for background.")
    parser.add_argument("--aia-pattern", default="*.fits", help="AIA FITS glob pattern.")
    parser.add_argument(
        "--max-aia-dt-sec",
        type=float,
        default=3600.0,
        help="Maximum AIA/radio frame time difference.",
    )
    parser.add_argument("--aia-max-pixels", type=int, default=1024)
    parser.add_argument("--aia-linear", action="store_true", help="Disable log10 AIA scaling.")
    parser.add_argument("--aia-wcs-mode", choices=["header", "sunpy"], default="header")
    return parser


def main(argv: list[str] | None = None) -> Path:
    """Run the static trajectory export."""

    args = build_parser().parse_args(argv)
    centers = load_centers_table(args.centers)
    centers = filter_centers(
        centers,
        freqs=_parse_float_list(args.freqs),
        polarizations=_parse_str_list(args.polarizations),
        center_methods=_parse_str_list(args.center_methods),
    )
    if centers.empty:
        raise ValueError("No center rows remain after filtering.")
    selected_frame_time = _resolve_frame_time(
        centers,
        frame_time=args.frame_time,
        frame_index=args.frame_index,
    )
    visible = select_visible_centers(
        centers,
        selected_frame_time,
        mode=args.mode,
        tail_n=args.tail_n,
    )

    aia_background = None
    title_extra = ""
    if args.aia_dir:
        aia_table = scan_aia_folder(args.aia_dir, pattern=args.aia_pattern)
        aia_background, nearest = load_nearest_background(
            aia_table,
            selected_frame_time,
            max_dt_seconds=args.max_aia_dt_sec,
            max_pixels=args.aia_max_pixels,
            log_scale=not args.aia_linear,
            wcs_mode=args.aia_wcs_mode,
        )
        if nearest.status == "matched":
            title_extra = f"AIA dt={nearest.delta_seconds:.1f}s"
        else:
            title_extra = f"AIA skipped: {nearest.status}"

    fig, _compare = build_trajectory_figure(
        visible,
        selected_frame_time,
        aia_background=aia_background,
        draw_lines=not args.no_lines,
        compare_lr=args.compare_lr,
        compare_tolerance_sec=args.compare_tolerance_sec,
        title_extra=title_extra,
    )
    out = export_trajectory_html(fig, args.out)
    print(f"Trajectory HTML: {out}")
    return out


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
    main()
