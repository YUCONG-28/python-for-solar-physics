from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from solar_toolkit.aia.background import AiaBackground
from solar_toolkit.visualization.radio_source_trajectory import (
    aia_plotly_colorscale,
    build_trajectory_figure,
    export_trajectory_html,
)


@pytest.fixture(autouse=True)
def _requires_plotly():
    pytest.importorskip(
        "plotly", reason="Plotly is an optional visualization dependency"
    )


def test_builds_plotly_trajectory_with_aia_background_and_lr_segments(tmp_path):
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "LCP",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37.200"),
                "freq_mhz": 149.0,
                "polarization": "RCP",
                "center_method": "threshold",
                "center_x_arcsec": 14.0,
                "center_y_arcsec": 25.0,
            },
        ]
    )
    background = AiaBackground(
        path="synthetic_aia.fits",
        z=np.ones((2, 2), dtype=float),
        x_arcsec=np.array([0.0, 2.0]),
        y_arcsec=np.array([0.0, 2.0]),
        label="synthetic AIA | 171 A",
        obs_time=pd.Timestamp("2025-01-24T04:48:37"),
        wavelength="171",
    )

    fig, compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37.200"),
        aia_background=background,
        draw_lines=True,
        compare_lr=True,
        compare_tolerance_sec=1.0,
    )
    out = export_trajectory_html(fig, tmp_path / "trajectory.html")

    assert len(fig.data) == 4
    assert fig.data[0].type == "heatmap"
    assert fig.data[0].colorscale == aia_plotly_colorscale("171")
    assert len(compare) == 1
    assert out.exists()
    assert "<html" in out.read_text(encoding="utf-8").lower()


def test_trajectory_figure_supports_theme_screen_fit_and_webgl():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:38"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 11.0,
                "center_y_arcsec": 21.0,
            },
        ]
    )

    dark_fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:38"),
        theme_mode="dark",
        screen_fit="portrait",
        use_webgl=True,
    )
    light_fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:38"),
        theme_mode="light",
        screen_fit="landscape",
        use_webgl=False,
    )

    assert dark_fig.data[0].type == "scattergl"
    assert dark_fig.layout.height > light_fig.layout.height
    assert dark_fig.layout.paper_bgcolor == "#0f172a"
    assert light_fig.data[0].type == "scatter"
    assert light_fig.layout.paper_bgcolor == "#ffffff"


def test_trajectory_figure_supports_frequency_facets_with_shared_axes():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:38"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 11.0,
                "center_y_arcsec": 21.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:38"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -7.0,
                "center_y_arcsec": 16.0,
            },
        ]
    )

    fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:38"),
        plot_layout="facets",
        facet_by="freq_mhz",
        use_webgl=True,
    )

    scatter_traces = [trace for trace in fig.data if trace.type == "scattergl"]
    assert len(scatter_traces) == 2
    assert {trace.xaxis for trace in scatter_traces} == {"x", "x2"}
    assert fig.layout.xaxis.range == fig.layout.xaxis2.range
    assert fig.layout.yaxis.range == fig.layout.yaxis2.range
    assert any("149" in annotation.text for annotation in fig.layout.annotations)
    assert any("164" in annotation.text for annotation in fig.layout.annotations)


def test_trajectory_figure_increases_facet_spacing_and_height_for_grid():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": float(freq),
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": float(index),
                "center_y_arcsec": float(index),
            }
            for index, freq in enumerate([149, 164, 190, 223, 238, 285, 300, 309, 324])
        ]
    )

    fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        plot_layout="facets",
        facet_by="freq_mhz",
        screen_fit="auto",
    )
    overlay, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        plot_layout="overlay",
        screen_fit="auto",
    )

    horizontal_gap = fig.layout.xaxis2.domain[0] - fig.layout.xaxis.domain[1]
    vertical_gap = fig.layout.yaxis.domain[0] - fig.layout.yaxis4.domain[1]

    assert horizontal_gap >= 0.07
    assert vertical_gap >= 0.12
    assert fig.layout.height > overlay.layout.height


def test_trajectory_figure_uses_time_fade_and_custom_marker_size():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:36"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 11.0,
                "center_y_arcsec": 21.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:38"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 12.0,
                "center_y_arcsec": 22.0,
            },
        ]
    )

    fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:38"),
        marker_size=14,
        trail_min_opacity=0.2,
    )

    trace = fig.data[0]
    assert trace.marker.size == 14
    assert list(trace.marker.opacity) == pytest.approx([0.2, 0.6, 1.0])


def test_trajectory_figure_uses_frequency_marker_symbols_and_time_annotation():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
        ]
    )

    fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        marker_symbol_by_freq={"149": "x", "164": "triangle-up"},
    )

    symbols = {
        float(trace.name.split(" MHz", 1)[0]): trace.marker.symbol for trace in fig.data
    }
    assert symbols == {149.0: "x", 164.0: "triangle-up"}
    assert any(
        "Radio source time: 2025-01-24T04:48:37" in annotation.text
        for annotation in fig.layout.annotations
    )


def test_trajectory_figure_can_sync_facet_axes():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
        ]
    )

    independent, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        plot_layout="facets",
        facet_by="freq_mhz",
        sync_axes=False,
    )
    synced, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        plot_layout="facets",
        facet_by="freq_mhz",
        sync_axes=True,
    )

    assert independent.layout.xaxis2.matches is None
    assert independent.layout.yaxis2.matches is None
    assert synced.layout.xaxis2.matches == "x"
    assert synced.layout.yaxis2.matches == "y"


def test_trajectory_figure_facets_preserve_aia_aspect_ratio():
    visible = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:37"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
        ]
    )
    background = AiaBackground(
        path="synthetic_aia.fits",
        z=np.ones((3, 5), dtype=float),
        x_arcsec=np.array([-1200.0, 0.0, 1200.0]),
        y_arcsec=np.array([-800.0, 0.0, 800.0]),
        label="synthetic AIA | 171 A",
        obs_time=pd.Timestamp("2025-01-24T04:48:37"),
        wavelength="171",
    )

    fig, _compare = build_trajectory_figure(
        visible,
        pd.Timestamp("2025-01-24T04:48:37"),
        aia_background=background,
        plot_layout="facets",
        facet_by="freq_mhz",
    )

    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1
    assert fig.layout.yaxis.constrain == "domain"
    assert fig.layout.yaxis2.scaleanchor == "x2"
    assert fig.layout.yaxis2.scaleratio == 1
    assert fig.layout.yaxis2.constrain == "domain"
