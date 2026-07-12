from __future__ import annotations

import json


def test_analysis_subdir_encodes_percentile_and_position():
    from solar_toolkit.radio.rrll_percentile_preview_comparison import _analysis_subdir

    assert _analysis_subdir(
        "rrll_spec_percentile_compare_20260712_r01",
        (95.0, 99.99),
        "middle",
    ) == (
        "radio_source_maps_9band_rrll_spec_percentile_compare_20260712_r01"
        "_p95_9999_preview_middle"
    )


def test_resolve_available_run_tag_skips_existing_target(tmp_path):
    from solar_toolkit.radio.rrll_percentile_preview_comparison import (
        _analysis_subdir,
        resolve_available_run_tag,
    )

    (tmp_path / _analysis_subdir("rrll_spec_percentile_compare_20260712_r01", (99.0, 99.99), "first")).mkdir(
        parents=True
    )

    assert (
        resolve_available_run_tag(tmp_path, "rrll_spec_percentile_compare_20260712")
        == "rrll_spec_percentile_compare_20260712_r02"
    )


def test_provenance_records_fixed_band_ranges(tmp_path):
    from solar_toolkit.radio.provenance import write_radio_provenance

    path = write_radio_provenance(
        tmp_path,
        {
            "display": {
                "color_range_mode": "fixed_per_band",
                "fixed_band_vmins": [1.0, 2.0],
                "fixed_band_vmaxs": [3.0, 4.0],
                "per_band_percentiles": [95.0, 99.99],
            }
        },
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    thresholds = payload["science"]["thresholds"]
    assert thresholds["display.color_range_mode"] == "fixed_per_band"
    assert thresholds["display.fixed_band_vmins"] == [1.0, 2.0]
    assert thresholds["display.fixed_band_vmaxs"] == [3.0, 4.0]
