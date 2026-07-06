from __future__ import annotations

import numpy as np
import pandas as pd

from solar_toolkit.aia.background import AiaBackground
from solar_toolkit.visualization.radio_source_trajectory import (
    build_trajectory_figure,
    export_trajectory_html,
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
    assert len(compare) == 1
    assert out.exists()
    assert "<html" in out.read_text(encoding="utf-8").lower()
