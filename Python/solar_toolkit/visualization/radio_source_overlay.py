"""Static radio-source overlays with optional AIA context."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

__all__ = ["render_radio_source_overlay_png"]


def render_radio_source_overlay_png(
    centers: pd.DataFrame,
    out_path: str | Path,
    *,
    frame_time,
    aia_background=None,
    width: int = 1200,
    height: int = 900,
    theme_mode: str = "light",
    draw_lines: bool = True,
    marker_size: int = 10,
    marker_symbol_by_freq: dict[str, str] | None = None,
    trail_min_opacity: float = 0.25,
    title_prefix: str = "Radio source overlay",
) -> Path:
    """Write one non-interactive overlay without application-layer imports."""

    if centers is None or centers.empty:
        raise ValueError("At least one radio-source center is required.")
    resolved_width = max(320, int(width))
    resolved_height = max(240, int(height))
    axis = _axis_limits(centers)
    if aia_background is not None:
        axis = _axis_limits_with_background(axis, aia_background)

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba

    theme = _theme_palette(theme_mode)
    dpi = 100
    fig, ax = plt.subplots(
        figsize=(resolved_width / dpi, resolved_height / dpi),
        dpi=dpi,
        facecolor=theme["paper_bgcolor"],
    )
    try:
        ax.set_facecolor(theme["plot_bgcolor"])
        ax.set_title(
            f"{title_prefix} | {pd.Timestamp(frame_time).isoformat()}",
            color=theme["font_color"],
            fontsize=12,
        )
        ax.set_xlim(*axis["x"])
        ax.set_ylim(*axis["y"])
        ax.set_aspect("equal", adjustable="box")
        ax.grid(color=theme["grid_color"], linewidth=0.6)
        ax.tick_params(colors=theme["font_color"], labelsize=8)
        ax.set_xlabel("HPLN / arcsec", color=theme["font_color"])
        ax.set_ylabel("HPLT / arcsec", color=theme["font_color"])
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

        groups = centers.groupby(
            ["freq_mhz", "polarization", "center_method"], sort=True
        )
        color_map = matplotlib.colormaps["tab10"]
        for index, ((freq, _pol, _method), group) in enumerate(groups):
            ordered = group.sort_values("obs_time")
            x = ordered["center_x_arcsec"].astype(float).to_numpy()
            y = ordered["center_y_arcsec"].astype(float).to_numpy()
            color = color_map(index % color_map.N)
            if draw_lines:
                ax.plot(x, y, color=color, linewidth=1.4, alpha=0.65)
            alphas = _trail_opacity(len(ordered), min_opacity=trail_min_opacity)
            ax.scatter(
                x,
                y,
                s=max(1, int(marker_size)) ** 2,
                marker=_matplotlib_marker_symbol(
                    _marker_symbol_for_frequency(freq, marker_symbol_by_freq)
                ),
                c=[to_rgba(color, alpha) for alpha in alphas],
            )
        fig.tight_layout()
        output = Path(out_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=dpi)
        return output
    finally:
        plt.close(fig)


def _theme_palette(theme_mode: object) -> dict[str, str]:
    if str(theme_mode or "auto").strip().casefold() == "dark":
        return {
            "paper_bgcolor": "#0b1120",
            "plot_bgcolor": "#111a2c",
            "font_color": "#e7edf7",
            "grid_color": "#33435d",
        }
    return {
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#f4f7fb",
        "font_color": "#172033",
        "grid_color": "#c9d4e3",
    }


def _axis_limits(centers: pd.DataFrame) -> dict[str, tuple[float, float]]:
    xs = centers["center_x_arcsec"].astype(float).to_numpy()
    ys = centers["center_y_arcsec"].astype(float).to_numpy()
    x0, x1 = float(np.nanmin(xs)), float(np.nanmax(xs))
    y0, y1 = float(np.nanmin(ys)), float(np.nanmax(ys))
    x_pad = max(1.0, (x1 - x0) * 0.05)
    y_pad = max(1.0, (y1 - y0) * 0.05)
    return {"x": (x0 - x_pad, x1 + x_pad), "y": (y0 - y_pad, y1 + y_pad)}


def _axis_limits_with_background(
    axis: dict[str, tuple[float, float]], background
) -> dict[str, tuple[float, float]]:
    return {
        "x": (
            min(axis["x"][0], float(np.nanmin(background.x_arcsec))),
            max(axis["x"][1], float(np.nanmax(background.x_arcsec))),
        ),
        "y": (
            min(axis["y"][0], float(np.nanmin(background.y_arcsec))),
            max(axis["y"][1], float(np.nanmax(background.y_arcsec))),
        ),
    }


def _frequency_key(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return (
        str(int(number))
        if np.isfinite(number) and number.is_integer()
        else f"{number:g}"
    )


def _marker_symbol_for_frequency(
    frequency: object, configured: dict[str, str] | None
) -> str:
    if not isinstance(configured, dict):
        return "circle"
    return str(configured.get(_frequency_key(frequency), "circle"))


def _matplotlib_marker_symbol(symbol: str) -> str:
    return {
        "circle": "o",
        "x": "x",
        "cross": "+",
        "triangle-up": "^",
        "square": "s",
        "diamond": "D",
    }.get(symbol, "o")


def _trail_opacity(count: int, *, min_opacity: float) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [1.0]
    low = min(1.0, max(0.0, float(min_opacity)))
    step = (1.0 - low) / float(count - 1)
    return [low + step * index for index in range(count)]
