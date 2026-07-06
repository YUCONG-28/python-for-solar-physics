"""MP4 export helpers for radio-source trajectory playback."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from solar_toolkit.aia.background import find_nearest_aia, read_aia_background
from solar_toolkit.radio.trajectory import select_visible_centers
from solar_toolkit.visualization.radio_source_trajectory import (
    FACET_BY_OPTIONS,
    PLOT_LAYOUTS,
    resolve_theme_palette,
)


@dataclass(frozen=True)
class VideoExportOptions:
    out_path: str | Path
    fps: float = 6.0
    width: int = 1280
    height: int = 720
    theme_mode: str = "auto"
    draw_lines: bool = True
    marker_size: int = 9
    trail_min_opacity: float = 0.25
    include_aia: bool = True
    max_aia_dt_sec: float = 3600.0
    aia_max_pixels: int = 384
    percentile_limits: tuple[float, float] = (1.0, 99.7)
    log_scale: bool = True
    wcs_mode: str = "header"


def export_radio_source_video_mp4(
    centers: pd.DataFrame,
    times: list[Any],
    *,
    frame_mode: str,
    tail_n: int,
    plot_layout: str,
    facet_by: str,
    options: VideoExportOptions,
    aia_table: pd.DataFrame | None = None,
    background_loader=None,
) -> Path:
    """Export the current radio-source playback state to an MP4 file."""

    import cv2

    normalized_times = [pd.Timestamp(value) for value in times]
    if not normalized_times:
        raise ValueError("At least one playback time is required for MP4 export.")
    out_path = Path(options.out_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width = max(320, int(options.width))
    height = max(240, int(options.height))
    fps = max(0.2, float(options.fps))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {out_path}")

    resolved_layout = _choice_value(PLOT_LAYOUTS, plot_layout, "overlay")
    resolved_facet_by = _choice_value(FACET_BY_OPTIONS, facet_by, "freq_mhz")
    axis = _axis_limits(centers)
    facet_values = (
        _facet_values(centers, resolved_facet_by) if resolved_layout == "facets" else []
    )
    background_loader = background_loader or read_aia_background

    try:
        for frame_time in normalized_times:
            visible = select_visible_centers(
                centers,
                frame_time,
                mode=frame_mode,
                tail_n=int(tail_n),
            )
            aia_background = None
            if options.include_aia and aia_table is not None and not aia_table.empty:
                nearest = find_nearest_aia(
                    aia_table,
                    frame_time,
                    max_dt_seconds=float(options.max_aia_dt_sec),
                )
                if nearest.status == "matched" and nearest.path:
                    aia_background = background_loader(
                        nearest.path,
                        max_pixels=int(options.aia_max_pixels),
                        percentile_limits=tuple(options.percentile_limits),
                        log_scale=bool(options.log_scale),
                        wcs_mode=options.wcs_mode,
                    )
            rgb = _render_frame_rgb(
                visible,
                frame_time,
                width=width,
                height=height,
                theme_mode=options.theme_mode,
                draw_lines=bool(options.draw_lines),
                marker_size=int(options.marker_size),
                trail_min_opacity=float(options.trail_min_opacity),
                plot_layout=resolved_layout,
                facet_by=resolved_facet_by,
                facet_values=facet_values,
                axis=axis,
                aia_background=aia_background,
            )
            writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()
    return out_path


def _render_frame_rgb(
    visible: pd.DataFrame,
    frame_time: pd.Timestamp,
    *,
    width: int,
    height: int,
    theme_mode: str,
    draw_lines: bool,
    marker_size: int,
    trail_min_opacity: float,
    plot_layout: str,
    facet_by: str,
    facet_values: list[object],
    axis: dict[str, tuple[float, float]],
    aia_background,
) -> np.ndarray:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    theme = resolve_theme_palette(theme_mode)
    dpi = 100
    fig = plt.figure(
        figsize=(width / dpi, height / dpi),
        dpi=dpi,
        facecolor=theme["paper_bgcolor"],
    )
    fig.suptitle(
        f"Radio source trajectory | {pd.Timestamp(frame_time).isoformat()}",
        color=theme["font_color"],
        fontsize=12,
    )
    if plot_layout == "facets" and facet_values:
        cols = min(3, max(1, len(facet_values)))
        rows = int(math.ceil(len(facet_values) / cols))
        axes = fig.subplots(rows, cols, squeeze=False)
        for index, facet_value in enumerate(facet_values):
            row = index // cols
            col = index % cols
            ax = axes[row][col]
            subset = visible[visible[facet_by].astype(str) == str(facet_value)]
            _draw_axes(
                ax,
                subset,
                axis=axis,
                title=_format_facet_label(facet_by, facet_value),
                theme=theme,
                draw_lines=draw_lines,
                marker_size=marker_size,
                trail_min_opacity=trail_min_opacity,
                aia_background=aia_background,
            )
        for index in range(len(facet_values), rows * cols):
            axes[index // cols][index % cols].set_visible(False)
    else:
        ax = fig.subplots(1, 1)
        _draw_axes(
            ax,
            visible,
            axis=axis,
            title="Overlay",
            theme=theme,
            draw_lines=draw_lines,
            marker_size=marker_size,
            trail_min_opacity=trail_min_opacity,
            aia_background=aia_background,
        )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    rgb = np.ascontiguousarray(rgba[:, :, :3])
    plt.close(fig)
    return rgb


def _draw_axes(
    ax,
    visible: pd.DataFrame,
    *,
    axis: dict[str, tuple[float, float]],
    title: str,
    theme: dict[str, str],
    draw_lines: bool,
    marker_size: int,
    trail_min_opacity: float,
    aia_background,
) -> None:
    ax.set_facecolor(theme["plot_bgcolor"])
    ax.set_title(title, color=theme["font_color"], fontsize=10)
    ax.set_xlim(*axis["x"])
    ax.set_ylim(*axis["y"])
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color=theme["grid_color"], linewidth=0.6)
    ax.tick_params(colors=theme["font_color"], labelsize=8)
    ax.set_xlabel("HPLN / arcsec", color=theme["font_color"], fontsize=8)
    ax.set_ylabel("HPLT / arcsec", color=theme["font_color"], fontsize=8)
    for spine in ax.spines.values():
        spine.set_color(theme["grid_color"])
    if aia_background is not None:
        ax.imshow(
            aia_background.z,
            extent=[
                float(np.nanmin(aia_background.x_arcsec)),
                float(np.nanmax(aia_background.x_arcsec)),
                float(np.nanmin(aia_background.y_arcsec)),
                float(np.nanmax(aia_background.y_arcsec)),
            ],
            origin="lower",
            cmap="gray",
            aspect="auto",
            zorder=0,
        )
    if visible is None or visible.empty:
        return
    for (_freq, _pol, _method), group in visible.groupby(
        ["freq_mhz", "polarization", "center_method"],
        sort=True,
    ):
        ordered = group.sort_values("obs_time")
        x = ordered["center_x_arcsec"].astype(float).to_numpy()
        y = ordered["center_y_arcsec"].astype(float).to_numpy()
        if draw_lines:
            ax.plot(x, y, linewidth=1.4, alpha=0.65)
        ax.scatter(
            x,
            y,
            s=max(1, int(marker_size)) ** 2,
            alpha=_trail_opacity(len(ordered), min_opacity=trail_min_opacity),
        )


def _axis_limits(centers: pd.DataFrame) -> dict[str, tuple[float, float]]:
    if centers is None or centers.empty:
        return {"x": (-1.0, 1.0), "y": (-1.0, 1.0)}
    xs = centers["center_x_arcsec"].astype(float).to_numpy()
    ys = centers["center_y_arcsec"].astype(float).to_numpy()
    x0, x1 = float(np.nanmin(xs)), float(np.nanmax(xs))
    y0, y1 = float(np.nanmin(ys)), float(np.nanmax(ys))
    x_pad = max(1.0, (x1 - x0) * 0.05)
    y_pad = max(1.0, (y1 - y0) * 0.05)
    return {"x": (x0 - x_pad, x1 + x_pad), "y": (y0 - y_pad, y1 + y_pad)}


def _facet_values(centers: pd.DataFrame, facet_by: str) -> list[object]:
    if facet_by not in centers.columns:
        return []
    values = centers[facet_by].dropna().unique().tolist()
    if facet_by == "freq_mhz":
        return sorted(values, key=lambda value: float(value))
    return sorted(values, key=lambda value: str(value))


def _format_facet_label(facet_by: str, value: object) -> str:
    if facet_by == "freq_mhz":
        return f"{float(value):.3g} MHz"
    if facet_by == "polarization":
        return f"Polarization: {value}"
    if facet_by == "center_method":
        return f"Method: {value}"
    return str(value)


def _choice_value(options: tuple[str, ...], value: object, default: str) -> str:
    text = str(value)
    return text if text in options else default


def _trail_opacity(count: int, *, min_opacity: float) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [1.0]
    low = min(1.0, max(0.0, float(min_opacity)))
    step = (1.0 - low) / float(count - 1)
    return [low + step * index for index in range(count)]
