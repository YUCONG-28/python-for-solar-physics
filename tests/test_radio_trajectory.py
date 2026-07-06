from __future__ import annotations

import pandas as pd
import pytest

from solar_toolkit.radio.trajectory import (
    FRAME_MODE_CURRENT,
    FRAME_MODE_TAIL,
    load_centers_table,
    make_lr_compare_table,
    normalize_centers_dataframe,
    select_visible_centers,
)


def test_normalizes_threshold_and_gaussian_center_tables(tmp_path):
    threshold_csv = tmp_path / "threshold_centers.csv"
    pd.DataFrame(
        [
            {
                "obs_time": "2025-01-24T04:48:37.681",
                "freq_mhz": 149.0,
                "polarization": "L+R",
                "center_method": "threshold_weighted_bg_peak_0.95",
                "center_x_arcsec": 10.0,
                "center_y_arcsec": 20.0,
            }
        ]
    ).to_csv(threshold_csv, index=False)

    threshold_df = load_centers_table(threshold_csv)

    assert list(threshold_df.columns[:7]) == [
        "obs_time",
        "freq_mhz",
        "polarization",
        "center_x_arcsec",
        "center_y_arcsec",
        "center_method",
        "quality_flag",
    ]
    assert threshold_df.loc[0, "quality_flag"] == "ok"

    gaussian = pd.DataFrame(
        [
            {
                "time": "20250124044837681",
                "freq": 164.0,
                "polarization": "RR+LL",
                "center_x_arcsec": 30.0,
                "center_y_arcsec": 40.0,
                "quality_flag": "ok",
                "overlay_valid": True,
                "trajectory_valid": True,
            },
            {
                "time": "20250124044838681",
                "freq": 164.0,
                "polarization": "RR+LL",
                "center_x_arcsec": 300.0,
                "center_y_arcsec": 400.0,
                "quality_flag": "bad_fit",
                "overlay_valid": False,
                "trajectory_valid": False,
            },
        ]
    )

    gaussian_df = normalize_centers_dataframe(gaussian, valid_only=True)

    assert len(gaussian_df) == 1
    assert gaussian_df.loc[0, "freq_mhz"] == pytest.approx(164.0)
    assert gaussian_df.loc[0, "center_method"] == "gaussian"
    assert gaussian_df.loc[0, "source_label"] == "main"


def test_selects_current_tail_and_lcp_rcp_comparison_rows():
    df = normalize_centers_dataframe(
        pd.DataFrame(
            [
                {
                    "obs_time": "2025-01-24T04:48:37",
                    "freq_mhz": 149.0,
                    "polarization": "LCP",
                    "center_method": "threshold",
                    "center_x_arcsec": 10.0,
                    "center_y_arcsec": 20.0,
                },
                {
                    "obs_time": "2025-01-24T04:48:38",
                    "freq_mhz": 149.0,
                    "polarization": "LCP",
                    "center_method": "threshold",
                    "center_x_arcsec": 11.0,
                    "center_y_arcsec": 21.0,
                },
                {
                    "obs_time": "2025-01-24T04:48:38.200",
                    "freq_mhz": 149.0,
                    "polarization": "RCP",
                    "center_method": "threshold",
                    "center_x_arcsec": 14.0,
                    "center_y_arcsec": 25.0,
                },
                {
                    "obs_time": "2025-01-24T04:48:39",
                    "freq_mhz": 164.0,
                    "polarization": "L+R",
                    "center_method": "gaussian",
                    "center_x_arcsec": 30.0,
                    "center_y_arcsec": 40.0,
                },
            ]
        )
    )

    current = select_visible_centers(
        df,
        pd.Timestamp("2025-01-24T04:48:38.500"),
        mode=FRAME_MODE_CURRENT,
    )
    tail = select_visible_centers(
        df,
        pd.Timestamp("2025-01-24T04:48:38.500"),
        mode=FRAME_MODE_TAIL,
        tail_n=2,
    )
    compare = make_lr_compare_table(tail, tolerance_sec=1.0)

    assert len(current) == 2
    assert current[current["polarization"] == "LCP"].iloc[0]["center_x_arcsec"] == 11.0
    assert len(tail[tail["polarization"] == "LCP"]) == 2
    assert len(compare) == 1
    assert compare.loc[0, "dx_L_minus_R_arcsec"] == pytest.approx(-3.0)
    assert compare.loc[0, "distance_arcsec"] == pytest.approx(5.0)
