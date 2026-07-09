from __future__ import annotations

import cv2
import pandas as pd
import pytest

from solar_toolkit.visualization.radio_source_video import (
    VideoExportOptions,
    export_radio_source_video_mp4,
)


def test_export_radio_source_video_mp4_writes_playable_file(tmp_path):
    centers = pd.DataFrame(
        [
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:45"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:46"),
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": 12.0,
                "center_y_arcsec": 22.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:45"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -8.0,
                "center_y_arcsec": 15.0,
            },
            {
                "obs_time": pd.Timestamp("2025-01-24T04:48:46"),
                "freq_mhz": 164.0,
                "polarization": "L+R",
                "center_method": "threshold",
                "center_x_arcsec": -6.0,
                "center_y_arcsec": 17.0,
            },
        ]
    )
    out = tmp_path / "trajectory.mp4"

    result = export_radio_source_video_mp4(
        centers,
        [
            pd.Timestamp("2025-01-24T04:48:45"),
            pd.Timestamp("2025-01-24T04:48:46"),
        ],
        frame_mode="tail",
        tail_n=1,
        plot_layout="facets",
        facet_by="freq_mhz",
        options=VideoExportOptions(
            out_path=out,
            fps=2.0,
            width=480,
            height=320,
            theme_mode="dark",
            draw_lines=True,
            include_aia=False,
            marker_size=12,
            marker_symbol_by_freq={"149": "x", "164": "triangle-up"},
            trail_min_opacity=0.35,
        ),
    )

    assert result == out.resolve()
    assert result.exists()
    assert result.stat().st_size > 0

    capture = cv2.VideoCapture(str(result))
    try:
        if not capture.isOpened():
            pytest.skip("OpenCV cannot reopen the generated mp4 on this platform")
        assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) >= 2
    finally:
        capture.release()
