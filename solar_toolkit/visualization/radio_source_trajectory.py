"""Plotly visualization for radio-source center trajectories.

English: Build an interactive radio-source trajectory figure with optional AIA
backgrounds, tail/current/all frame modes, LCP-RCP comparison, and HTML export.

中文：生成交互式射电源中心轨迹图，支持 AIA 背景、当前/尾迹/全轨迹显示、
LCP-RCP 对比以及单文件 HTML 导出。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from solar_toolkit.aia.background import AiaBackground
from solar_toolkit.radio.trajectory import make_lr_compare_table


def _go():
    import plotly.graph_objects as go

    return go


def build_trajectory_figure(
    visible: pd.DataFrame,
    frame_time,
    *,
    aia_background: AiaBackground | None = None,
    draw_lines: bool = True,
    compare_lr: bool = False,
    compare_tolerance_sec: float = 1.0,
    title_extra: str = "",
    height: int = 760,
):
    """Build a Plotly figure for one radio-source playback frame."""

    go = _go()
    fig = go.Figure()

    if aia_background is not None:
        fig.add_trace(
            go.Heatmap(
                z=aia_background.z,
                x=aia_background.x_arcsec,
                y=aia_background.y_arcsec,
                colorscale="gray",
                showscale=False,
                name="AIA",
                hovertemplate='x=%{x:.1f}"<br>y=%{y:.1f}"<extra>AIA</extra>',
            )
        )

    mode = "lines+markers" if draw_lines else "markers"
    if visible is not None and not visible.empty:
        for (freq, pol, method), group in visible.groupby(
            ["freq_mhz", "polarization", "center_method"],
            sort=True,
        ):
            sorted_group = group.sort_values("obs_time")
            hover = [
                _center_hover_text(row, freq=freq, pol=pol, method=method)
                for _, row in sorted_group.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=sorted_group["center_x_arcsec"],
                    y=sorted_group["center_y_arcsec"],
                    mode=mode,
                    marker={"size": 9},
                    line={"width": 2},
                    name=f"{float(freq):.3g} MHz | {pol} | {method}",
                    text=hover,
                    hovertemplate="%{text}<extra></extra>",
                )
            )

    compare_df = pd.DataFrame()
    if compare_lr and visible is not None and not visible.empty:
        compare_df = make_lr_compare_table(
            visible,
            tolerance_sec=float(compare_tolerance_sec),
        )
        add_lr_compare_segments(fig, compare_df)

    title = (
        "Radio source trajectory | "
        f"display time: {pd.Timestamp(frame_time).isoformat()}"
    )
    if title_extra:
        title = f"{title} | {title_extra}"
    fig.update_layout(
        title=title,
        xaxis_title="HPLN / arcsec",
        yaxis_title="HPLT / arcsec",
        height=int(height),
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 30, "r": 30, "t": 85, "b": 30},
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig, compare_df


def _center_hover_text(row: pd.Series, *, freq: float, pol: str, method: str) -> str:
    return (
        f"time={pd.Timestamp(row['obs_time']).isoformat()}"
        f"<br>freq={float(freq):.3g} MHz"
        f"<br>pol={pol}"
        f"<br>method={method}"
        f"<br>x={float(row['center_x_arcsec']):.2f}\""
        f"<br>y={float(row['center_y_arcsec']):.2f}\""
    )


def add_lr_compare_segments(fig, compare_df: pd.DataFrame) -> None:
    """Add dotted LCP-RCP separation segments to an existing figure."""

    if compare_df is None or compare_df.empty:
        return
    go = _go()
    xs: list[float | None] = []
    ys: list[float | None] = []
    hover: list[str] = []
    for _, row in compare_df.iterrows():
        xs.extend([row["L_x_arcsec"], row["R_x_arcsec"], None])
        ys.extend([row["L_y_arcsec"], row["R_y_arcsec"], None])
        text = (
            f"{float(row['freq_mhz']):.3g} MHz"
            f"<br>{pd.Timestamp(row['obs_time']).isoformat()}"
            f"<br>|L-R|={float(row['distance_arcsec']):.2f} arcsec"
        )
        hover.extend([text, text, ""])
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name="LCP-RCP separation",
            line={"width": 1, "dash": "dot"},
            hovertext=hover,
            hoverinfo="text",
        )
    )


def export_trajectory_html(
    fig,
    out: str | Path,
    *,
    include_plotlyjs: str | bool = "cdn",
) -> Path:
    """Write a Plotly trajectory figure to a standalone HTML file."""

    output_path = Path(out).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(output_path),
        include_plotlyjs=include_plotlyjs,
        full_html=True,
    )
    return output_path
