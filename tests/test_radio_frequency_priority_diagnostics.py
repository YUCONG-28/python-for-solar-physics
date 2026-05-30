from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure

import scripts.radio.core.radio_frequency_priority_diagnostics as diagnostics
from scripts.radio.configs import (
    load_radio_config_module,
    load_radio_diagnostic_presentation_config,
    load_radio_user_config,
)
from scripts.radio.core.radio_frequency_priority_diagnostics import (
    apply_frequency_priority_drift_matching,
    build_frequency_priority_summary,
    build_newkirk_physical_consistency_report,
    build_selected_band_newkirk_height_speed_table,
    format_newkirk_case_label,
    plot_event_gaussian_newkirk_height_comparison,
    plot_event_newkirk_speed_frequency,
    plot_frequency_priority_summary,
    plot_gaussian_center_by_frequency_facets,
    plot_gaussian_center_trajectory_by_frequency,
    plot_height_time_by_frequency_facets,
    write_frequency_priority_dashboard,
)
from scripts.radio.run_radio_burst_pipeline import _plot_drift_speed_comparison


def test_config_uses_gaussian_multiband_frequencies():
    cfg = load_radio_diagnostic_presentation_config("radio_20250124_config")

    assert cfg["comparison_frequency_mhz"] == [149, 164, 190, 205, 223, 238]
    assert cfg["reverse_frequency_axis"] is False


def test_event_config_is_single_source_for_legacy_exports():
    module = load_radio_config_module("radio_20250124_config")
    legacy_aia_module = load_radio_config_module("aia_radio_hmi_20250124_config")
    user_config, newkirk_config = load_radio_user_config("radio_20250124_config")
    presentation = load_radio_diagnostic_presentation_config("radio_20250124_config")

    assert set(module.EVENT_CONFIG) >= {
        "user",
        "newkirk",
        "newkirk_height_comparison",
        "drift_selection_products",
        "diagnostic_presentation",
    }
    assert legacy_aia_module.AIA_RADIO_HMI_CONFIG is module.AIA_RADIO_HMI_CONFIG
    assert module.USER_CONFIG == module.EVENT_CONFIG["user"]
    assert module.NEWKIRK_CONFIG == module.EVENT_CONFIG["newkirk"]
    assert user_config == module.EVENT_CONFIG["user"]
    assert newkirk_config["solar_radius_arcsec"] == 959.63
    assert presentation["enable_static_summary"] is False
    assert presentation["enable_html_dashboard"] is False
    assert (
        presentation["event_height_comparison_name"]
        == "event_gaussian_newkirk_height_comparison.png"
    )
    assert (
        presentation["event_speed_frequency_name"]
        == "event_newkirk_speed_frequency_scatter.png"
    )
    assert (
        presentation["selected_band_newkirk_table_name"]
        == "event_selected_band_newkirk_table.csv"
    )


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


def test_height_time_facets_report_newkirk_reference_lines():
    with tempfile.TemporaryDirectory() as tmp:
        result = plot_height_time_by_frequency_facets(
            pd.DataFrame(
                [
                    _height_row(149, 0.10, 0.09, 2, 2),
                    _height_row(164, 0.20, 0.19, 2, 2),
                ]
            ),
            Path(tmp) / "height_time_by_frequency_facets.png",
            {
                "comparison_frequency_mhz": [149, 164],
                "selected_newkirk_multiplier": 2.0,
                "selected_newkirk_harmonic": 2,
            },
        )

        assert result["status"] == "saved"
        assert result["newkirk_reference_line_count"] == 2
        assert result["newkirk_reference_model_label"] == "2× Newkirk, s=2"


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
        assert "Frequency-Priority Dashboard" in dashboard_html.read_text(
            encoding="utf-8"
        )


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


def test_center_facets_report_solar_radius_annotation_config():
    gaussian_df = pd.DataFrame([_gaussian_row("2025-01-24T04:48:40", 149.0)])
    with tempfile.TemporaryDirectory() as tmp:
        result = plot_gaussian_center_by_frequency_facets(
            gaussian_df,
            Path(tmp) / "gaussian_center_by_frequency_facets.png",
            {"comparison_frequency_mhz": [149], "solar_radius_arcsec": 959.63},
        )

        assert result["status"] == "saved"
        assert result["solar_radius_arcsec"] == pytest_approx(959.63)
        assert result["color_meaning"] == "Time (UT)"


def test_time_colored_trajectory_outputs_one_file_per_frequency():
    gaussian_df = pd.DataFrame(
        [
            _gaussian_row("2025-01-24T04:48:40", 149.0),
            _gaussian_row("2025-01-24T04:48:41", 149.0),
            _gaussian_row("2025-01-24T04:48:42", 164.0),
            _gaussian_row("2025-01-24T04:48:43", 164.0),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = plot_gaussian_center_trajectory_by_frequency(
            gaussian_df,
            Path(tmp),
            {"comparison_frequency_mhz": [149, 164]},
        )

        assert result["status"] == "saved"
        assert result["cross_frequency_line_count"] == 0
        assert sorted(Path(path).name for path in result["paths"]) == [
            "gaussian_center_trajectory_time_colored_149MHz.png",
            "gaussian_center_trajectory_time_colored_164MHz.png",
        ]


def test_selected_band_newkirk_table_has_speed_for_matched_drift_and_status_for_unmatched():
    drift_df = pd.DataFrame(
        [
            {
                "label": "drift_001",
                "t_start": "2025-01-24T04:48:39",
                "t_end": "2025-01-24T04:48:41",
                "f_start_mhz": 160.0,
                "f_end_mhz": 138.0,
                "drift_rate_mhz_s": -11.0,
            }
        ]
    )

    out = build_selected_band_newkirk_height_speed_table(
        drift_df,
        {
            "comparison_frequency_mhz": [149, 238],
            "selected_newkirk_multiplier": 2.0,
            "selected_newkirk_harmonic": 2,
            "drift_frequency_tolerance_mhz": 12.0,
        },
    )

    matched = out[out["frequency_mhz"].eq(149.0)].iloc[0]
    unmatched = out[out["frequency_mhz"].eq(238.0)].iloc[0]
    assert matched["drift_label"] == "drift_001"
    assert math.isfinite(matched["newkirk_speed_km_s"])
    assert matched["newkirk_speed_c"] == pytest_approx(
        matched["newkirk_speed_km_s"] / 299792.458
    )
    assert matched["effective_density_factor"] == pytest_approx(8.0)
    assert matched["newkirk_assumption_label"] == "2x Newkirk, H=2, N*s^2=8"
    assert matched["speed_status"] == "ok"
    assert unmatched["speed_status"] == "no_matching_drift_rate"
    assert math.isnan(unmatched["newkirk_speed_km_s"])


def test_event_height_comparison_uses_only_selected_newkirk_model(monkeypatch):
    height_df = pd.DataFrame(
        [
            _height_row(149, 0.10, 0.02, 1, 1),
            _height_row(149, 0.10, 0.10, 1, 2),
            _height_row(149, 0.10, 0.19, 2, 1),
            _height_row(149, 0.10, 0.30, 2, 2),
            _height_row(149, 0.10, 0.43, 4, 1),
            _height_row(149, 0.10, 0.48, 4, 2),
            _height_row(164, 0.20, 0.04, 1, 1),
            _height_row(164, 0.20, 0.12, 1, 2),
            _height_row(164, 0.20, 0.21, 2, 1),
            _height_row(164, 0.20, 0.32, 2, 2),
            _height_row(164, 0.20, 0.46, 4, 1),
            _height_row(164, 0.20, 0.50, 4, 2),
        ]
    )
    captured = {}

    def capture_save(fig, output_path, **savefig_kwargs):
        captured["ax"] = fig.axes[0]

    monkeypatch.setattr(diagnostics, "_save", capture_save)

    result = plot_event_gaussian_newkirk_height_comparison(
        height_df,
        Path("event_gaussian_newkirk_height_comparison.png"),
        {
            "comparison_frequency_mhz": [149, 164],
            "selected_newkirk_multiplier": 2.0,
            "selected_newkirk_harmonic": 2,
            "reverse_frequency_axis": False,
        },
    )

    ax = captured["ax"]
    x_left, x_right = ax.get_xlim()
    legend_text = " ".join(text.get_text() for text in ax.get_legend().get_texts())
    plot_text = " ".join(text.get_text() for text in ax.texts)

    assert result["status"] == "saved"
    assert result["selected_model_label"] == "2xH2"
    assert result["newkirk_model_count"] == 6
    assert result["gaussian_frequency_count"] == 2
    assert x_left < x_right
    assert "Gaussian centers" in legend_text
    assert "Gaussian median +/- IQR" in legend_text
    assert "Reference Newkirk model" in legend_text
    assert "2x Newkirk / harmonic" not in legend_text
    assert "1x F" in plot_text
    assert "2x H ref" in plot_text
    assert "4x H" in plot_text
    assert "F = fundamental (H=1), H = harmonic (H=2)" in " ".join(
        text.get_text() for text in ax.figure.texts
    )


def test_event_speed_frequency_plots_only_matched_frequency_rows():
    speed_df = pd.DataFrame(
        [
            {
                "frequency_mhz": 149.0,
                "newkirk_speed_km_s": 50000.0,
                "newkirk_speed_c": 0.17,
                "speed_status": "ok",
                "drift_label": "drift_001",
                "newkirk_assumption_label": "2x Newkirk, H=2, N*s^2=8",
            },
            {
                "frequency_mhz": 238.0,
                "newkirk_speed_km_s": float("nan"),
                "newkirk_speed_c": float("nan"),
                "speed_status": "no_matching_drift_rate",
                "drift_label": "",
                "newkirk_assumption_label": "2x Newkirk, H=2, N*s^2=8",
            },
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = plot_event_newkirk_speed_frequency(
            speed_df,
            Path(tmp) / "event_newkirk_speed_frequency_scatter.png",
            {"reverse_frequency_axis": True, "connect_same_drift_only": True},
        )

        assert result["status"] == "saved"
        assert result["plotted_frequency_count"] == 1
        assert result["skipped_frequency_count"] == 1
        assert result["cross_drift_line_count"] == 0


def test_event_speed_frequency_marks_unmatched_frequency_and_pads_labels(monkeypatch):
    speed_df = pd.DataFrame(
        [
            {
                "frequency_mhz": 149.0,
                "newkirk_speed_km_s": 53700.0,
                "newkirk_speed_c": 0.18,
                "speed_status": "ok",
                "drift_label": "drift_001",
                "drift_rate_mhz_s": -25.1719235164734,
                "newkirk_assumption_label": "2x Newkirk, H=2, N*s^2=8",
            },
            {
                "frequency_mhz": 164.0,
                "newkirk_speed_km_s": 46100.0,
                "newkirk_speed_c": 0.15,
                "speed_status": "ok",
                "drift_label": "drift_001",
                "drift_rate_mhz_s": -25.1719235164734,
                "newkirk_assumption_label": "2x Newkirk, H=2, N*s^2=8",
            },
            {
                "frequency_mhz": 205.0,
                "newkirk_speed_km_s": float("nan"),
                "newkirk_speed_c": float("nan"),
                "speed_status": "no_matching_drift_rate",
                "drift_label": "",
                "newkirk_assumption_label": "2x Newkirk, H=2, N*s^2=8",
            },
        ]
    )
    captured = {}

    def capture_save(fig, output_path, **savefig_kwargs):
        captured["ax"] = fig.axes[0]
        captured["savefig_kwargs"] = savefig_kwargs

    monkeypatch.setattr(diagnostics, "_save", capture_save)

    result = diagnostics.plot_event_newkirk_speed_frequency(
        speed_df,
        Path("event_newkirk_speed_frequency_scatter.png"),
        {"reverse_frequency_axis": False, "connect_same_drift_only": True},
    )

    ax = captured["ax"]
    x_left, x_right = ax.get_xlim()
    y_bottom, y_top = ax.get_ylim()

    assert result["status"] == "saved"
    assert result["plotted_frequency_count"] == 2
    assert result["skipped_frequency_count"] == 1
    assert result["unmatched_frequency_count"] == 1
    assert x_left < 149.0
    assert x_right > 205.0
    assert y_top > 53700.0
    assert captured["savefig_kwargs"]["bbox_inches"] == "tight"
    assert any("205 MHz: no drift" in text.get_text() for text in ax.texts)
    assert any("df/dt=-25.17 MHz/s" in text.get_text() for text in ax.texts)
    assert len(ax.lines) == 0
    legend = ax.get_legend()
    assert legend is not None
    assert "2x Newkirk" in legend.get_title().get_text()
    assert "harmonic" in legend.get_title().get_text()
    assert "H=2" in legend.get_title().get_text()
    assert "N*s^2=8" in legend.get_title().get_text()
    assert any(
        "drift_001, df/dt=-25.17 MHz/s" in text.get_text()
        for text in legend.get_texts()
    )


def test_newkirk_case_label_describes_density_and_emission_mode():
    assert format_newkirk_case_label(2, 2) == "2x Newkirk / harmonic (H=2), N*s^2=8"
    assert (
        format_newkirk_case_label(1, 1, compact=True)
        == "1x Newkirk\nfundamental H=1\nN*s^2=1"
    )


def test_drift_speed_heatmap_labels_models_and_drift_rates(monkeypatch):
    speed_df = pd.DataFrame(
        [
            {
                "label": "drift_001",
                "drift_rate_mhz_s": -25.1719235164734,
                "newkirk_multiplier": 2.0,
                "newkirk_harmonic": 2.0,
                "newkirk_speed_km_s": 53700.0,
                "newkirk_speed_c": 0.18,
            }
        ]
    )
    captured = {}

    def capture_savefig(self, path, *args, **kwargs):
        captured["ax"] = self.axes[0]

    monkeypatch.setattr(Figure, "savefig", capture_savefig)

    _plot_drift_speed_comparison(speed_df, Path("drift_newkirk_speed_comparison.png"))

    ax = captured["ax"]
    xlabels = [label.get_text() for label in ax.get_xticklabels()]
    ylabels = [label.get_text() for label in ax.get_yticklabels()]
    assert any(
        "2x Newkirk" in label and "harmonic H=2" in label and "N*s^2=8" in label
        for label in xlabels
    )
    assert any("drift_001\n-25.17 MHz/s" == label for label in ylabels)


def test_physical_consistency_report_summarizes_speed_height_and_invalid_points():
    speed_df = pd.DataFrame(
        [
            {
                "frequency_mhz": 149.0,
                "newkirk_speed_km_s": 50000.0,
                "newkirk_speed_c": 0.17,
                "speed_status": "ok",
                "drift_label": "drift_001",
            }
        ]
    )
    height_summary = pd.DataFrame(
        [
            {
                "frequency_mhz": 149.0,
                "gaussian_valid_count": 1,
                "gaussian_invalid_count": 1,
                "gaussian_projected_height_median_rsun": 0.30,
                "gaussian_projected_height_q25_rsun": 0.25,
                "gaussian_projected_height_q75_rsun": 0.35,
                "newkirk_height_rsun_2xH2": 0.32,
                "abs_delta_reference_rsun": 0.02,
                "relative_delta_reference": 0.0625,
            }
        ]
    )

    report = build_newkirk_physical_consistency_report(
        speed_df,
        height_summary,
        {"reference_newkirk_assumption": "2xH2"},
    )

    assert "Speed range summary" in report
    assert "plausible type III / spike-associated exciter range" in report
    assert "Invalid Gaussian points summary" in report
    assert (
        "model-inferred exciter speeds rather than direct radio source bulk motions"
        in report
    )


def _height_row(
    freq,
    gaussian_height,
    newkirk_height,
    multiplier,
    harmonic,
    time="2025-01-24T04:48:40",
):
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
