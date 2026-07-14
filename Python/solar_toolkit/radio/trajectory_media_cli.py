"""Export filtered radio-source trajectories as MP4, GIF, or WebM media.

The module keeps its scientific and media imports inside :func:`run` so the
CLI help path stays lightweight. Optional AIA backgrounds use the same
package-owned matcher and renderer as the compatibility trajectory app.
"""

from __future__ import annotations

import argparse
from pathlib import Path

__all__ = ["build_parser", "main", "run"]

_FORMATS = ("mp4", "gif", "webm")
_FRAME_MODES = ("current", "tail", "all")
_PLOT_LAYOUTS = ("overlay", "facets")
_FACET_BY_OPTIONS = ("freq_mhz", "polarization", "center_method")
_THEMES = ("auto", "light", "dark")


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone trajectory-media argument parser."""

    parser = argparse.ArgumentParser(
        description="Export a filtered radio-source trajectory as local media.",
        epilog="AIA backgrounds are optional and remain local to the selected folder.",
    )
    parser.add_argument("--centers", required=True, help="Input center CSV/XLSX table.")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Workspace-managed output directory; default is the current directory.",
    )
    parser.add_argument("--format", choices=_FORMATS, default="mp4")
    parser.add_argument("--freqs", help="Comma-separated frequencies in MHz.")
    parser.add_argument("--polarizations", help="Comma-separated polarizations.")
    parser.add_argument("--center-methods", help="Comma-separated center methods.")
    parser.add_argument("--frame-mode", choices=_FRAME_MODES, default="tail")
    parser.add_argument("--tail-n", type=_positive_int, default=5)
    parser.add_argument("--plot-layout", choices=_PLOT_LAYOUTS, default="overlay")
    parser.add_argument("--facet-by", choices=_FACET_BY_OPTIONS, default="freq_mhz")
    parser.add_argument("--fps", type=_positive_float, default=6.0)
    parser.add_argument("--width", type=_positive_int, default=1280)
    parser.add_argument("--height", type=_positive_int, default=720)
    parser.add_argument("--theme", choices=_THEMES, default="auto")
    parser.add_argument("--marker-size", type=_positive_int, default=9)
    parser.add_argument("--aia-dir", help="Optional folder of AIA FITS backgrounds.")
    parser.add_argument("--aia-pattern", default="*.fits")
    parser.add_argument("--use-aia", action="store_true")
    parser.add_argument("--max-aia-dt-sec", type=_positive_float, default=3600.0)
    parser.add_argument("--aia-max-pixels", type=_positive_int, default=384)
    parser.add_argument(
        "--start-frame",
        type=_non_negative_int,
        default=0,
        help="Zero-based first frame index (inclusive).",
    )
    parser.add_argument(
        "--end-frame",
        type=_positive_int,
        help="Zero-based stop frame index (exclusive); default exports through the end.",
    )
    return parser


def run(
    centers_path: str | Path,
    output_dir: str | Path = ".",
    *,
    output_format: str = "mp4",
    freqs: list[float] | tuple[float, ...] | None = None,
    polarizations: list[str] | tuple[str, ...] | None = None,
    center_methods: list[str] | tuple[str, ...] | None = None,
    frame_mode: str = "tail",
    tail_n: int = 5,
    plot_layout: str = "overlay",
    facet_by: str = "freq_mhz",
    fps: float = 6.0,
    width: int = 1280,
    height: int = 720,
    theme: str = "auto",
    marker_size: int = 9,
    start_frame: int = 0,
    end_frame: int | None = None,
    aia_dir: str | Path | None = None,
    aia_pattern: str = "*.fits",
    use_aia: bool = False,
    max_aia_dt_sec: float = 3600.0,
    aia_max_pixels: int = 384,
) -> Path:
    """Filter center rows and export the selected playback frames.

    ``start_frame`` is inclusive and ``end_frame`` is exclusive. AIA matching
    is enabled only when both ``use_aia`` and ``aia_dir`` are supplied.
    """

    resolved_format = _choice("output_format", output_format, _FORMATS)
    resolved_frame_mode = _choice("frame_mode", frame_mode, _FRAME_MODES)
    resolved_layout = _choice("plot_layout", plot_layout, _PLOT_LAYOUTS)
    resolved_facet = _choice("facet_by", facet_by, _FACET_BY_OPTIONS)
    resolved_theme = _choice("theme", theme, _THEMES)
    _require_positive("tail_n", tail_n)
    _require_positive("fps", fps)
    _require_positive("width", width)
    _require_positive("height", height)
    _require_positive("marker_size", marker_size)
    if int(start_frame) < 0:
        raise ValueError("start_frame must be zero or greater.")
    if end_frame is not None and int(end_frame) <= int(start_frame):
        raise ValueError("end_frame must be greater than start_frame.")
    _require_positive("max_aia_dt_sec", max_aia_dt_sec)
    _require_positive("aia_max_pixels", aia_max_pixels)

    # Lazy imports keep ``python -m ... --help`` free of NumPy/Pandas imports.
    from solar_toolkit.aia.background import scan_aia_folder
    from solar_toolkit.radio.trajectory import (
        filter_centers,
        frame_times,
        load_centers_table,
    )
    from solar_toolkit.visualization.radio_source_video import (
        VideoExportOptions,
        export_radio_source_video,
    )

    centers = load_centers_table(centers_path)
    centers = filter_centers(
        centers,
        freqs=freqs,
        polarizations=polarizations,
        center_methods=center_methods,
    )
    if centers.empty:
        raise ValueError("No center rows remain after filtering.")
    times = frame_times(centers)
    if not times:
        raise ValueError("No valid playback times remain after filtering.")
    if int(start_frame) >= len(times):
        raise ValueError("start_frame is outside the available playback frames.")

    workspace_dir = Path(output_dir).expanduser().resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    output_path = workspace_dir / f"radio_source_trajectory.{resolved_format}"
    options = VideoExportOptions(
        out_path=output_path,
        output_format=resolved_format,
        fps=float(fps),
        width=int(width),
        height=int(height),
        theme_mode=resolved_theme,
        marker_size=int(marker_size),
        include_aia=bool(use_aia and aia_dir),
        max_aia_dt_sec=float(max_aia_dt_sec),
        aia_max_pixels=int(aia_max_pixels),
        start_frame=int(start_frame),
        end_frame=None if end_frame is None else int(end_frame),
    )
    aia_table = (
        scan_aia_folder(aia_dir, pattern=aia_pattern)
        if bool(use_aia and aia_dir)
        else None
    )
    return export_radio_source_video(
        centers,
        times,
        frame_mode=resolved_frame_mode,
        tail_n=int(tail_n),
        plot_layout=resolved_layout,
        facet_by=resolved_facet,
        options=options,
        aia_table=aia_table,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the trajectory-media command and print the generated path."""

    args = build_parser().parse_args(argv)
    output_path = run(
        centers_path=args.centers,
        output_dir=args.output_dir,
        output_format=args.format,
        freqs=_parse_float_list(args.freqs),
        polarizations=_parse_str_list(args.polarizations),
        center_methods=_parse_str_list(args.center_methods),
        frame_mode=args.frame_mode,
        tail_n=args.tail_n,
        plot_layout=args.plot_layout,
        facet_by=args.facet_by,
        fps=args.fps,
        width=args.width,
        height=args.height,
        theme=args.theme,
        marker_size=args.marker_size,
        start_frame=args.start_frame,
        end_frame=args.end_frame,
        aia_dir=args.aia_dir,
        aia_pattern=args.aia_pattern,
        use_aia=args.use_aia,
        max_aia_dt_sec=args.max_aia_dt_sec,
        aia_max_pixels=args.aia_max_pixels,
    )
    print(f"Trajectory media: {output_path}")
    return 0


def _parse_str_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None


def _parse_float_list(raw: str | None) -> list[float] | None:
    values = _parse_str_list(raw)
    return None if values is None else [float(value) for value in values]


def _choice(name: str, value: str, choices: tuple[str, ...]) -> str:
    resolved = str(value).strip().lower()
    if resolved not in choices:
        raise ValueError(f"{name} must be one of: {', '.join(choices)}.")
    return resolved


def _require_positive(name: str, value: int | float) -> None:
    if float(value) <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return value


def _non_negative_int(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return value


def _positive_float(raw: str) -> float:
    value = float(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
