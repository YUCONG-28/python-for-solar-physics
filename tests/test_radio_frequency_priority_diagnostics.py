from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd

from scripts.radio.configs import load_radio_diagnostic_presentation_config
from scripts.radio.core.radio_frequency_priority_diagnostics import (
    apply_frequency_priority_drift_matching,
    build_frequency_priority_summary,
    model_label,
    plot_frequency_priority_summary,
    plot_gaussian_center_by_frequency_facets,
    plot_height_time_by_frequency_facets,
    write_frequency_priority_dashboard,
)


def test_config_uses_gaussian_multiband_frequencies():
    cfg = load_radio_diagnostic_presentation_config("radio_20250124_config")

    assert cfg["comparison_frequency_mhz"] == [149, 164, 190, 205, 223, 238]


def test_summary_uses_only_configured_gaussian_frequency_bands():
    height_df = pd.DataFrame(
        [
            _height_row(149, 0.10, 0.08, 1, 1),
            _height_row(164, 0.20, 0.18, 1, 1),
            _height_row(999, 0.90, 0.02, 1, 1),
        ]
    )

    summary = build_frequency_priority_summary(
        height_df,
        pd.DataFrame(),
        pd.DataFrame(),
        {"comparison_frequency_mhz": [149, 164]},
    )

    assert summary["comparison_frequency_mhz"] == [149.0, 164.0]
    assert set(summary["gaussian_height_summary"]["frequency_mhz"]) == {149.0, 164.0}
    assert set(summary["residual_summary"]["frequency_mhz"]) == {149.0, 164.0}


def test_model_scoring_uses_observed_frequency_bands_only():
    height_df = pd.DataFrame(
        [
            _height_row(149, 0.10, 0.10, 2, 2),
            _height_row(164, 0.20, 0.19, 2, 2),
            _height_row(999, 0.20, 2.00, 2, 2),
            _height_row(149, 0.10, 0.40, 1, 1),
            _height_row(164, 0.20, 0.50, 1, 1),
        ]
    )

    summary = build_frequency_priority_summary(
        height_df,
        pd.DataFrame(),
        pd.DataFrame(),
        {"comparison_frequency_mhz": [149, 164]},
    )

    best = summary["model_ranking"].iloc[0]
    assert best["model_label"] == "2× Newkirk, s=2"
    assert best["median_abs_residual_rsun"] < 0.02


def test_drift_matching_applies_label_map_and_preserves_unknown_for_unmatched():
    gaussian_df = pd.DataFrame(
        [
            _gaussian_row("2025-01-24T04:48:40", 149.0),
            _gaussian_row("2025-01-24T04:48:50", 238.0),
        ]
    )
    drift_df = pd.DataFrame(
        [
            {
                "label": "drift_001",
                "t_start": "2025-01-24T04:48:39",
                "t_end": "2025-01-24T04:48:41",
                "f_start_mhz": 160.0,
                "f_end_mhz": 138.0,
            }
        ]
    )

    out = apply_frequency_priority_drift_matching(
        gaussian_df,
        drift_df,
        {
            "comparison_frequency_mhz": [149, 238],
            "drift_source_type_map": {"drift_001": "typeIII"},
            "drift_time_tolerance_s": 0.75,
            "drift_frequency_tolerance_mhz": 12.0,
        },
    )

    assert out.iloc[0]["drift_label"] == "drift_001"
    assert out.iloc[0]["source_type"] == "typeIII"
    assert out.iloc[0]["drift_match_warning"] == ""
    assert out.iloc[1]["drift_label"] == ""
    assert out.iloc[1]["source_type"] == "unknown"


def test_height_time_facets_do_not_connect_across_frequency_bands():
    with tempfile.TemporaryDirectory() as tmp:
        result = plot_height_time_by_frequency_facets(
            pd.DataFrame(
                [
                    _height_row(149, 0.10, 0.09, 2, 2),
                    _height_row(164, 0.20, 0.19, 2, 2),
                    _height_row(149, 0.12, 0.11, 2, 2, time="2025-01-24T04:48:41"),
                ]
            ),
            Path(tmp) / "height_time_by_frequency_facets.png",
            {"comparison_frequency_mhz": [149, 164]},
        )

        assert result["status"] == "saved"
        assert result["cross_frequency_line_count"] == 0


def test_static_summary_and_dashboard_are_written_without_plotly():
    height_df = pd.DataFrame(
        [
            _height_row(149, 0.10, 0.09, 2, 2),
            _height_row(164, 0.20, 0.19, 2, 2),
            _height_row(149, 0.10, 0.30, 1, 1),
            _height_row(164, 0.20, 0.40, 1, 1),
        ]
    )
    gaussian_df = pd.DataFrame(
        [
            _gaussian_row("2025-01-24T04:48:40", 149.0),
            _gaussian_row("2025-01-24T04:48:41", 164.0),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        summary_png = out / "radio_newkirk_frequency_priority_summary.png"
        dashboard_html = out / "radio_newkirk_frequency_priority_dashboard.html"

        fig_result = plot_frequency_priority_summary(
            height_df,
            gaussian_df,
            pd.DataFrame(),
            summary_png,
            {"comparison_frequency_mhz": [149, 164]},
        )
        html_result = write_frequency_priority_dashboard(
            height_df,
            gaussian_df,
            pd.DataFrame(),
            dashboard_html,
            {"comparison_frequency_mhz": [149, 164]},
        )

        assert fig_result["status"] == "saved"
        assert summary_png.exists()
        assert html_result["status"] == "saved"
        assert dashboard_html.exists()
        assert "Frequency-Priority Dashboard" in dashboard_html.read_text(encoding="utf-8")


def test_center_facets_accept_radio_compact_time_strings():
    gaussian_df = pd.DataFrame(
        [
            {
                "time": "20250124044829509",
                "freq": 149.0,
                "center_x_arcsec": 1200.0,
                "center_y_arcsec": -300.0,
                "quality_flag": "ok",
            }
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "gaussian_center_by_frequency_facets.png"
        result = plot_gaussian_center_by_frequency_facets(
            gaussian_df,
            path,
            {"comparison_frequency_mhz": [149]},
        )

        assert result["status"] == "saved"
        assert path.exists()


def _height_row(freq, gaussian_height, newkirk_height, multiplier, harmonic, time="2025-01-24T04:48:40"):
    return {
        "time": time,
        "frequency_mhz": float(freq),
        "source_type": "unknown",
        "drift_label": "",
        "gaussian_x_arcsec": 1200.0 + float(freq) / 10.0,
        "gaussian_y_arcsec": -300.0,
        "gaussian_height_rsun": gaussian_height,
        "newkirk_multiplier": float(multiplier),
        "harmonic": int(harmonic),
        "newkirk_height_rsun": newkirk_height,
        "height_residual_rsun": gaussian_height - newkirk_height,
        "height_valid": True,
    }


def _gaussian_row(time, freq):
    return {
        "time": time,
        "freq": freq,
        "center_x_arcsec": 1200.0,
        "center_y_arcsec": -300.0,
        "quality_flag": "ok",
        "overlay_valid": True,
        "trajectory_valid": True,
    }


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
