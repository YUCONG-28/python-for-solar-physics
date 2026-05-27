from __future__ import annotations

import math

import numpy as np
import pandas as pd

from scripts.radio.core.radio_newkirk_spatial import (
    build_newkirk_spatial_dataframe,
    compute_gaussian_newkirk_residuals,
    project_newkirk_radius_from_gaussian_anchor,
)


def _gaussian_rows():
    return pd.DataFrame(
        [
            {
                "time": "2025-01-24T04:48:40",
                "freq": 220.0,
                "center_x_arcsec": 240.0,
                "center_y_arcsec": 180.0,
                "fwhm_major_arcsec": 80.0,
                "fwhm_minor_arcsec": 45.0,
                "theta_rad": 0.25,
                "quality_flag": "ok",
                "overlay_valid": True,
                "trajectory_valid": True,
            },
            {
                "time": "2025-01-24T04:48:45",
                "freq": 120.0,
                "center_x_arcsec": 240.0,
                "center_y_arcsec": 180.0,
                "quality_flag": "ok",
                "overlay_valid": True,
                "trajectory_valid": True,
            },
        ]
    )


def test_lower_frequency_gives_larger_newkirk_radius():
    out = build_newkirk_spatial_dataframe(
        _gaussian_rows(),
        {
            "solar_radius_arcsec": 960.0,
            "harmonic": 1,
            "newkirk_multiplier": 1.0,
        },
    ).sort_values("frequency_mhz")

    assert out.iloc[0]["frequency_mhz"] == 120.0
    assert out.iloc[0]["newkirk_radius_rsun"] > out.iloc[1]["newkirk_radius_rsun"]


def test_radial_projection_preserves_direction():
    row = _gaussian_rows().iloc[0].to_dict()
    projected = project_newkirk_radius_from_gaussian_anchor(
        row,
        solar_radius_arcsec=960.0,
        harmonic=1,
        newkirk_multiplier=1.0,
    )

    assert projected["geometry_valid"] is True
    assert projected["newkirk_x_rsun"] / projected["newkirk_y_rsun"] == pytest_approx(
        row["center_x_arcsec"] / row["center_y_arcsec"]
    )


def test_identical_gaussian_and_newkirk_points_produce_zero_residual():
    row = {
        "gaussian_x_rsun": 0.25,
        "gaussian_y_rsun": 0.5,
        "newkirk_x_rsun": 0.25,
        "newkirk_y_rsun": 0.5,
        "gaussian_x_arcsec": 240.0,
        "gaussian_y_arcsec": 480.0,
        "newkirk_x_arcsec": 240.0,
        "newkirk_y_arcsec": 480.0,
    }

    residual = compute_gaussian_newkirk_residuals(row)

    assert residual["residual_rsun"] == pytest_approx(0.0)
    assert residual["residual_arcsec"] == pytest_approx(0.0)


def test_nan_inputs_do_not_crash():
    df = pd.DataFrame(
        [
            {
                "time": "2025-01-24T04:48:40",
                "freq": np.nan,
                "center_x_arcsec": np.nan,
                "center_y_arcsec": 180.0,
                "quality_flag": "ok",
            }
        ]
    )

    out = build_newkirk_spatial_dataframe(df, {"solar_radius_arcsec": 960.0})

    assert len(out) == 1
    assert out.iloc[0]["geometry_valid"] == False
    assert isinstance(out.iloc[0]["geometry_reason"], str)


def test_near_disk_center_anchor_is_geometry_invalid():
    row = {
        "freq": 150.0,
        "center_x_arcsec": 1e-9,
        "center_y_arcsec": 1e-9,
        "quality_flag": "ok",
    }

    projected = project_newkirk_radius_from_gaussian_anchor(
        row,
        solar_radius_arcsec=960.0,
        harmonic=1,
        newkirk_multiplier=1.0,
    )

    assert projected["geometry_valid"] is False
    assert projected["geometry_reason"] == "anchor_too_close_to_disk_center"


def test_missing_source_type_falls_back_to_unknown():
    out = build_newkirk_spatial_dataframe(
        _gaussian_rows().head(1), {"solar_radius_arcsec": 960.0}
    )

    assert out.iloc[0]["source_type"] == "unknown"


def test_invalid_gaussian_row_is_kept_but_geometry_invalid():
    row = _gaussian_rows().head(1).copy()
    row.loc[row.index[0], "quality_flag"] = "low_snr"

    out = build_newkirk_spatial_dataframe(row, {"solar_radius_arcsec": 960.0})

    assert len(out) == 1
    assert out.iloc[0]["gaussian_fit_success"] == False
    assert out.iloc[0]["geometry_valid"] == False
    assert out.iloc[0]["geometry_reason"] == "invalid_gaussian_fit"


def pytest_approx(value):
    try:
        import pytest
    except ModuleNotFoundError:
        class Approx:
            def __eq__(self, other):
                return math.isclose(other, value, rel_tol=1e-12, abs_tol=1e-12)

        return Approx()

    return pytest.approx(value, rel=1e-12, abs=1e-12)


if __name__ == "__main__":
    for name, func in sorted(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
