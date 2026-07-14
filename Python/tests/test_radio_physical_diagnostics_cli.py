from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from solar_toolkit.radio.physical_diagnostics_cli import (
    build_drift_newkirk_table,
    build_parser,
    run_physical_diagnostics,
)


def _gaussian_row() -> dict:
    return {
        "source_file": "149MHz_test.fits",
        "time": "20250124044840000",
        "freq": 149.0,
        "polarization": "RR+LL",
        "center_x_arcsec": 1100.0,
        "center_y_arcsec": 0.0,
        "center_x_pixel": 128.0,
        "center_y_pixel": 128.0,
        "fwhm_valid": True,
        "overlay_valid": True,
        "trajectory_valid": True,
        "quality_flag": "ok",
        "quality_flag_detail": "",
    }


def _drift_row() -> dict:
    return {
        "drift_label": "drift_001",
        "t_start": "2025-01-24T04:48:40",
        "t_end": "2025-01-24T04:48:42",
        "f_start_mhz": 160.0,
        "f_end_mhz": 140.0,
        "drift_rate_mhz_s": -10.0,
        "quality_flag": "ok",
    }


def test_physical_diagnostics_reads_existing_tables_without_upstream_work(tmp_path):
    gaussian_path = tmp_path / "gaussian.csv"
    drift_path = tmp_path / "drift.csv"
    output = tmp_path / "physical"
    pd.DataFrame([_gaussian_row()]).to_csv(gaussian_path, index=False)
    pd.DataFrame([_drift_row()]).to_csv(drift_path, index=False)

    result = run_physical_diagnostics(
        gaussian_csv=gaussian_path,
        drift_csv=drift_path,
        config_name="radio_20250124_config",
        output_dir=output,
        workspace_config={
            "diagnostic_presentation": {
                "enable_static_summary": False,
                "enable_html_dashboard": False,
                "comparison_frequency_mhz": [149],
            }
        },
    )

    assert result["gaussian_input"] == str(gaussian_path)
    assert result["drift_input"] == str(drift_path)
    assert set(result["artifacts"]) >= {
        "height_rows_csv",
        "drift_speed_csv",
        "frequency_summary_csv",
        "physical_consistency_report",
    }
    assert all(Path(path).is_file() for path in result["artifacts"].values())
    drift_speed = pd.read_csv(result["artifacts"]["drift_speed_csv"])
    assert len(drift_speed) == 6
    assert set(drift_speed["newkirk_multiplier"]) == {1.0, 2.0, 4.0}
    assert set(drift_speed["newkirk_harmonic"]) == {1, 2}


def test_drift_builder_filters_rejected_quality_rows():
    rows = pd.DataFrame(
        [
            _drift_row(),
            {**_drift_row(), "drift_label": "rejected", "quality_flag": "bad"},
        ]
    )

    result = build_drift_newkirk_table(rows, {"multipliers": [2], "harmonics": [2]})

    assert result["drift_label"].tolist() == ["drift_001"]


def test_physical_cli_requires_at_least_one_existing_table(tmp_path):
    with pytest.raises(ValueError, match="gaussian-csv"):
        run_physical_diagnostics(output_dir=tmp_path)

    help_text = build_parser().format_help()
    assert "--gaussian-csv" in help_text
    assert "--drift-csv" in help_text
