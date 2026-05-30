from __future__ import annotations

import numpy as np

from scripts.radio.core.radio_gaussian_fit import (
    detect_gaussian_source_candidates,
    elliptical_gaussian_2d,
    fit_multiple_gaussians_on_radio_image,
    multi_gaussian_diagnostics_rows,
    save_multi_gaussian_diagnostics_row,
)
from scripts.radio.core.radio_io import (
    GAUSSIAN_DIAGNOSTIC_FIELDS,
    MULTI_GAUSSIAN_DIAGNOSTIC_FIELDS,
)


def _cfg(**overrides):
    cfg = {
        "fit_use_source_mask": True,
        "fit_snr_threshold": 2.0,
        "fit_grow_snr_threshold": 1.5,
        "fit_peak_fraction_threshold": 0.35,
        "fit_grow_peak_fraction_threshold": 0.20,
        "fit_mask_target_min_pixels": 8,
        "fit_mask_target_max_pixels": 500,
        "fit_peak_fraction_threshold_min": 0.25,
        "fit_peak_fraction_threshold_max": 0.60,
        "fit_peak_fraction_threshold_step": 0.05,
        "fit_min_mask_pixels": 6,
        "fit_mask_dilation_pixels": 1,
        "fit_background_model": "constant",
        "gaussian_fit_maxfev": 8000,
        "gaussian_fit_use_roi": True,
        "gaussian_fit_roi_padding_pixels": 5,
        "gaussian_fit_max_pixels": 800,
        "gaussian_fit_normalize_data": True,
        "gaussian_fit_fallback_to_moment": True,
        "max_sigma_fraction": 0.35,
        "skip_low_quality_fit": True,
        "multi_gaussian_max_sources": 3,
        "multi_gaussian_min_peak_fraction": 0.25,
        "multi_gaussian_min_peak_distance_pixels": 5,
        "multi_gaussian_use_watershed": True,
    }
    cfg.update(overrides)
    return cfg


def _image(shape=(64, 64), sources=()):
    y_pix = np.arange(shape[0], dtype=np.float64)
    x_pix = np.arange(shape[1], dtype=np.float64)
    x_grid, y_grid = np.meshgrid(x_pix, y_pix)
    data = np.full(shape, 0.05, dtype=np.float64)
    for source in sources:
        data += elliptical_gaussian_2d((x_grid, y_grid), *source)
    return data


def test_auto_multi_source_fit_recovers_two_separated_sources():
    data = _image(
        sources=[
            (9.0, 18.0, 24.0, 3.2, 2.6, 0.0),
            (6.5, 44.0, 38.0, 3.6, 2.8, 0.1),
        ]
    )

    result = fit_multiple_gaussians_on_radio_image(
        data,
        extent=(0.0, 64.0, 0.0, 64.0),
        cfg=_cfg(),
        source_file="two_sources.fits",
        image_origin="lower",
    )

    assert result.source_count_mode == "auto"
    assert result.detected_source_count == 2
    assert len(result.fit_results) == 2
    centers = sorted(
        (fit.center_pixel for fit in result.fit_results), key=lambda xy: xy[0]
    )
    np.testing.assert_allclose(centers[0], (18.0, 24.0), atol=1.25)
    np.testing.assert_allclose(centers[1], (44.0, 38.0), atol=1.25)
    assert result.primary_result is result.fit_results[0]


def test_requested_source_count_records_missing_sources():
    data = _image(sources=[(8.0, 30.0, 28.0, 3.0, 3.0, 0.0)])

    result = fit_multiple_gaussians_on_radio_image(
        data,
        extent=(0.0, 64.0, 0.0, 64.0),
        cfg=_cfg(multi_gaussian_source_count=2),
        source_file="one_source.fits",
        image_origin="lower",
    )
    rows = multi_gaussian_diagnostics_rows(
        result,
        _cfg(multi_gaussian_source_count=2),
        freq=150,
        time_str="2025-01-24T04:48:00",
        polarization="RR",
    )

    assert result.source_count_mode == "requested"
    assert result.requested_source_count == 2
    assert result.detected_source_count == 1
    assert result.missing_source_count == 1
    assert any(row["reason"] == "missing_requested_source" for row in rows)


def test_requested_single_source_count_uses_single_source_fit_path():
    data = _image(sources=[(8.0, 30.0, 28.0, 3.0, 3.0, 0.0)])

    result = fit_multiple_gaussians_on_radio_image(
        data,
        extent=(0.0, 64.0, 0.0, 64.0),
        cfg=_cfg(multi_gaussian_source_count=1),
        source_file="single_requested.fits",
        image_origin="lower",
    )

    assert result.source_count_mode == "requested"
    assert result.requested_source_count == 1
    assert result.detected_source_count == 1
    assert result.missing_source_count == 0
    assert len(result.fit_results) == 1
    np.testing.assert_allclose(
        result.primary_result.center_pixel, (30.0, 28.0), atol=1.0
    )


def test_candidate_detection_splits_nearby_peaks_until_min_distance_merges_them():
    data = _image(
        sources=[
            (8.0, 25.0, 30.0, 4.0, 3.0, 0.0),
            (7.0, 35.0, 30.0, 4.0, 3.0, 0.0),
        ]
    )

    split_candidates = detect_gaussian_source_candidates(
        data,
        extent=(0.0, 64.0, 0.0, 64.0),
        cfg=_cfg(multi_gaussian_min_peak_distance_pixels=5),
        image_origin="lower",
    )
    merged_candidates = detect_gaussian_source_candidates(
        data,
        extent=(0.0, 64.0, 0.0, 64.0),
        cfg=_cfg(multi_gaussian_min_peak_distance_pixels=20),
        image_origin="lower",
    )

    assert len(split_candidates) == 2
    assert len(merged_candidates) == 1


def test_multi_gaussian_fields_extend_legacy_gaussian_fields():
    assert MULTI_GAUSSIAN_DIAGNOSTIC_FIELDS[: len(GAUSSIAN_DIAGNOSTIC_FIELDS)] == (
        GAUSSIAN_DIAGNOSTIC_FIELDS
    )
    for field in (
        "source_id",
        "source_rank",
        "source_is_primary",
        "source_count_mode",
        "requested_source_count",
        "detected_source_count",
        "source_detection_snr",
        "source_candidate_pixel_count",
    ):
        assert field in MULTI_GAUSSIAN_DIAGNOSTIC_FIELDS


def test_multi_gaussian_csv_uses_extended_header(tmp_path):
    row = {field: "" for field in MULTI_GAUSSIAN_DIAGNOSTIC_FIELDS}
    row.update(
        {
            "source_file": "two_sources.fits",
            "quality_flag": "ok",
            "source_id": 1,
            "source_count_mode": "auto",
            "detected_source_count": 2,
        }
    )

    save_multi_gaussian_diagnostics_row(
        row,
        tmp_path,
        {
            "analysis_subdir": "gaussian_overlay",
            "multi_gaussian_diagnostics_csv": "multi.csv",
        },
    )

    csv_path = tmp_path / "gaussian_overlay" / "multi.csv"
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == MULTI_GAUSSIAN_DIAGNOSTIC_FIELDS
    assert header[: len(GAUSSIAN_DIAGNOSTIC_FIELDS)] == GAUSSIAN_DIAGNOSTIC_FIELDS
