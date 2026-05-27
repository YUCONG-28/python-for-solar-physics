"""AIA 171 spatial plots for Newkirk-projected radio source diagnostics."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse

from .radio_io import ensure_output_dir


def plot_aia171_typeIII_spike_newkirk_distribution(
    aia171_path,
    spatial_df,
    output_path,
    config=None,
):
    cfg = dict(config or {})
    path = Path(str(aia171_path)) if aia171_path else None
    if path is None or not path.exists():
        return {"status": "skipped", "reason": "missing_aia171_path", "path": str(aia171_path)}

    loaded = _load_aia171_image(path)
    if loaded["status"] != "ok":
        return loaded

    df = pd.DataFrame(spatial_df).copy()
    ensure_output_dir(Path(output_path).parent or ".")

    fig, ax = plt.subplots(figsize=cfg.get("figsize", (9, 8)), dpi=int(cfg.get("dpi", 180)))
    image = loaded["image"]
    extent = loaded["extent"]
    finite = image[np.isfinite(image)]
    vmin, vmax = (None, None)
    if finite.size:
        vmin, vmax = np.nanpercentile(finite, cfg.get("aia_percentiles", (1, 99.7)))
    ax.imshow(
        image,
        extent=extent,
        origin="lower",
        cmap=cfg.get("aia_cmap", "sdoaia171"),
        vmin=vmin,
        vmax=vmax,
        zorder=0,
    )

    valid = _geometry_valid_rows(df)
    color_values, color_label = _color_values(valid, cfg.get("color_by", "frequency"))
    norm = None
    if len(valid) and np.isfinite(color_values).any():
        norm = plt.Normalize(np.nanmin(color_values), np.nanmax(color_values))

    _draw_gaussian_centers(ax, valid, color_values, norm, cfg)
    _draw_gaussian_ellipses(ax, valid, cfg)
    sc = _draw_newkirk_points(ax, valid, color_values, norm, cfg)
    _draw_residual_arrows(ax, valid, cfg)
    _draw_typeiii_trajectory(ax, valid, cfg)

    if sc is not None:
        cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(color_label)
        if cfg.get("color_by", "frequency") == "time":
            cbar.ax.yaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))

    ax.text(
        0.02,
        0.02,
        "Newkirk spatial positions are projected using plane-of-sky radial anchoring from Gaussian radio centers.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="white",
        bbox={"facecolor": "black", "alpha": 0.45, "edgecolor": "none", "pad": 4},
    )
    ax.set_xlabel("Solar X (arcsec)")
    ax.set_ylabel("Solar Y (arcsec)")
    ax.set_title("AIA 171: type III/spike Newkirk spatial distribution")
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return {"status": "saved", "path": str(output_path), "rows_plotted": int(len(valid))}


def _load_aia171_image(path: Path) -> dict:
    try:
        import sunpy.map
    except Exception as exc:
        return {"status": "skipped", "reason": "sunpy_unavailable", "detail": str(exc)}
    try:
        smap = sunpy.map.Map(str(path))
        image = np.asarray(smap.data, dtype=float)
        extent = _map_extent_arcsec(smap)
    except Exception as exc:
        return {"status": "skipped", "reason": "aia_load_failed", "detail": str(exc)}
    if image.ndim != 2:
        return {"status": "skipped", "reason": "aia_data_not_2d"}
    image = np.log1p(np.clip(image, a_min=0, a_max=None))
    return {"status": "ok", "image": image, "extent": extent}


def _map_extent_arcsec(smap):
    ny, nx = smap.data.shape
    header = smap.meta
    x0, x1 = _pixel_to_arcsec([0, nx - 1], header, 1, nx)
    y0, y1 = _pixel_to_arcsec([0, ny - 1], header, 2, ny)
    return [min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)]


def _pixel_to_arcsec(pixels, header, axis, size):
    crpix = float(header.get(f"crpix{axis}", header.get(f"CRPIX{axis}", (size + 1) / 2.0)))
    cdelt = float(header.get(f"cdelt{axis}", header.get(f"CDELT{axis}", 1.0)))
    crval = float(header.get(f"crval{axis}", header.get(f"CRVAL{axis}", 0.0)))
    pix = np.asarray(pixels, dtype=float)
    return (pix + 1 - crpix) * cdelt + crval


def _geometry_valid_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "geometry_valid" not in df.columns:
        return pd.DataFrame()
    data = df[df["geometry_valid"].map(_truthy)].copy()
    for column in [
        "gaussian_x_arcsec",
        "gaussian_y_arcsec",
        "newkirk_x_arcsec",
        "newkirk_y_arcsec",
        "frequency_mhz",
    ]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    return data.dropna(
        subset=[
            "gaussian_x_arcsec",
            "gaussian_y_arcsec",
            "newkirk_x_arcsec",
            "newkirk_y_arcsec",
        ]
    )


def _color_values(df: pd.DataFrame, color_by: str):
    if df.empty:
        return np.asarray([], dtype=float), "Frequency (MHz)"
    if str(color_by).lower() == "time" and "time" in df.columns:
        times = pd.to_datetime(df["time"], errors="coerce")
        return mdates.date2num(times.dt.to_pydatetime()), "Time (UT)"
    return pd.to_numeric(df.get("frequency_mhz"), errors="coerce").to_numpy(dtype=float), "Frequency (MHz)"


def _draw_gaussian_centers(ax, df, color_values, norm, cfg):
    if df.empty:
        return
    ax.scatter(
        df["gaussian_x_arcsec"],
        df["gaussian_y_arcsec"],
        c=color_values,
        cmap=cfg.get("radio_cmap", "viridis"),
        norm=norm,
        marker="o",
        s=28,
        edgecolors="black",
        linewidths=0.4,
        label="Gaussian centers",
        zorder=3,
    )


def _draw_gaussian_ellipses(ax, df, cfg):
    if not cfg.get("draw_gaussian_ellipse", True):
        return
    for _, row in df.iterrows():
        major = _float_or_nan(row.get("gaussian_fwhm_major_arcsec"))
        minor = _float_or_nan(row.get("gaussian_fwhm_minor_arcsec"))
        if not np.isfinite(major) or not np.isfinite(minor):
            continue
        ellipse = Ellipse(
            (row["gaussian_x_arcsec"], row["gaussian_y_arcsec"]),
            width=major,
            height=minor,
            angle=_float_or_nan(row.get("gaussian_angle_deg")) or 0.0,
            fill=False,
            edgecolor=cfg.get("gaussian_ellipse_color", "white"),
            linewidth=0.9,
            alpha=0.75,
            zorder=2,
        )
        ax.add_patch(ellipse)


def _draw_newkirk_points(ax, df, color_values, norm, cfg):
    if df.empty:
        return None
    plotted = []
    sc = None
    for source_type, marker, label in [
        ("typeIII", "^", "Type III Newkirk"),
        ("spike", "s", "Spike Newkirk"),
        ("unknown", "x", "Unknown Newkirk"),
    ]:
        if source_type == "typeIII" and not cfg.get("plot_typeIII", True):
            continue
        if source_type == "spike" and not cfg.get("plot_spike", True):
            continue
        group = df[df.get("source_type", "unknown").astype(str).str.lower() == source_type.lower()]
        if group.empty:
            continue
        idx = group.index
        sc = ax.scatter(
            group["newkirk_x_arcsec"],
            group["newkirk_y_arcsec"],
            c=np.asarray(color_values)[df.index.get_indexer(idx)],
            cmap=cfg.get("radio_cmap", "viridis"),
            norm=norm,
            marker=marker,
            s=45,
            edgecolors="white" if marker != "x" else "none",
            linewidths=0.5,
            label=label,
            zorder=4,
        )
        plotted.append(sc)
    return sc or (plotted[-1] if plotted else None)


def _draw_residual_arrows(ax, df, cfg):
    if not cfg.get("draw_residual_arrows", True):
        return
    max_arrow = cfg.get("max_residual_arrow_arcsec")
    for _, row in df.iterrows():
        dx = row["newkirk_x_arcsec"] - row["gaussian_x_arcsec"]
        dy = row["newkirk_y_arcsec"] - row["gaussian_y_arcsec"]
        length = float(np.hypot(dx, dy))
        if max_arrow is not None and np.isfinite(length) and length > float(max_arrow):
            scale = float(max_arrow) / max(length, 1e-12)
            dx *= scale
            dy *= scale
        ax.arrow(
            row["gaussian_x_arcsec"],
            row["gaussian_y_arcsec"],
            dx,
            dy,
            length_includes_head=True,
            head_width=8,
            head_length=12,
            color="cyan",
            alpha=0.45,
            linewidth=0.7,
            zorder=3,
        )


def _draw_typeiii_trajectory(ax, df, cfg):
    if not cfg.get("plot_typeIII", True) or df.empty:
        return
    group = df[df.get("source_type", "unknown").astype(str).str.lower() == "typeiii"].copy()
    if len(group) < 2:
        return
    group["time_dt"] = pd.to_datetime(group["time"], errors="coerce")
    group = group.sort_values("time_dt")
    ax.plot(
        group["newkirk_x_arcsec"],
        group["newkirk_y_arcsec"],
        color=cfg.get("typeIII_line_color", "deepskyblue"),
        linewidth=1.4,
        alpha=0.9,
        label="Type III trajectory",
        zorder=5,
    )


def _float_or_nan(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok"}
    return bool(value)
