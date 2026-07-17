from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from astropy.io import fits

from solar_toolkit.radio.quality_science import (
    AUTOMATIC_QUALITY_RULE_VERSION,
    RadioScienceFeatureConfig,
    analyze_radio_science_quality,
    classify_scientific_quality,
    compute_context_similarity,
    compute_scientific_quality_features,
    write_radio_science_quality_csv,
)
from solar_toolkit.radio.raw_quality import RawFileQualityRow


def _header(*, frequency_mhz: float = 150.0, time: str = "2025-01-01T00:00:00"):
    header = fits.Header()
    header["CTYPE1"] = "HPLN-TAN"
    header["CTYPE2"] = "HPLT-TAN"
    header["CDELT1"] = 1.0
    header["CDELT2"] = 1.0
    header["DATE-OBS"] = time
    header["FREQ"] = frequency_mhz * 1.0e6
    return header


def _raw_row(path: Path, *, time: str, slot: int, polarization: str):
    return RawFileQualityRow(
        source_file=str(path),
        frequency_mhz=150.0,
        polarization=polarization,
        file_index=slot,
        slot_index=slot,
        time=time,
        quality_flag="ok",
        reason="within_group_baseline",
        total_pixel_count=64 * 64,
        finite_pixel_count=64 * 64,
        positive_pixel_count=64 * 64,
        finite_fraction=1.0,
        positive_fraction=1.0,
        p50=0.0,
        p95=0.0,
        p99=0.0,
        p997=0.0,
        p999=0.0,
        max_log10=0.0,
        baseline_p95=0.0,
        baseline_p997=0.0,
        p95_delta=0.0,
        p997_delta=0.0,
        bright_threshold_log10=0.0,
        bright_pixel_count=0,
        bright_component_count=0,
        largest_component_pixels=0,
        largest_component_bbox_width=0,
        largest_component_bbox_height=0,
        largest_component_fill_fraction=0.0,
        distributed_bright_fraction=0.0,
    )


def test_signed_features_preserve_negative_artifacts():
    rng = np.random.default_rng(11)
    data = rng.normal(0.0, 1.0, size=(96, 96))
    data[:, 20:22] -= 12.0
    data[42:50, 44:52] += 20.0

    features, thumbnail = compute_scientific_quality_features(
        data,
        _header(),
        expected_frequency_mhz=150.0,
        expected_time="2025-01-01T00:00:00",
    )

    assert features.data_valid
    assert features.negative_tail_fraction > 0.0
    assert features.negative_component_count >= 1
    assert features.negative_to_positive_peak_ratio > 0.0
    assert features.negative_to_positive_tail_energy_ratio > 0.0
    assert thumbnail is not None
    assert float(thumbnail.min()) < 0.0 < float(thumbnail.max())


def test_deterministic_invalid_data_is_a_hard_bad_candidate():
    features, thumbnail = compute_scientific_quality_features(np.ones((4, 4, 4)))
    decision = classify_scientific_quality(features)

    assert thumbnail is None
    assert decision.automatic_decision == "bad_candidate"
    assert decision.hard_invalid
    assert decision.rule_version == AUTOMATIC_QUALITY_RULE_VERSION


def test_compact_bright_source_is_not_bad_only_because_it_is_bright():
    yy, xx = np.indices((128, 128))
    data = np.random.default_rng(7).normal(0.0, 0.2, size=(128, 128))
    data += 30.0 * np.exp(-((xx - 64) ** 2 + (yy - 62) ** 2) / (2.0 * 5.0**2))
    features, _ = compute_scientific_quality_features(
        data,
        _header(),
        expected_frequency_mhz=150.0,
        expected_time="2025-01-01T00:00:00",
    )

    decision = classify_scientific_quality(features)

    assert decision.automatic_decision != "bad_candidate"
    assert not any("bright" in reason for reason in decision.automatic_reasons)


def test_frequency_metadata_mismatch_requires_human_review():
    data = np.random.default_rng(5).normal(size=(64, 64))
    features, _ = compute_scientific_quality_features(
        data,
        _header(frequency_mhz=327.0),
        expected_frequency_mhz=150.0,
        expected_time="2025-01-01T00:00:00",
    )

    decision = classify_scientific_quality(features)

    assert not features.frequency_metadata_valid
    assert decision.automatic_decision == "uncertain"
    assert "missing_or_inconsistent_frequency" in decision.automatic_reasons


def test_context_similarity_reports_signed_shape_disagreement():
    reference = np.arange(64, dtype=float).reshape(8, 8)
    correlation, residual = compute_context_similarity(reference, [-reference])

    assert math.isclose(correlation, -1.0)
    assert residual > 0.0


def test_analysis_uses_real_time_for_cross_channel_pairing_and_writes_csv(tmp_path):
    first = np.random.default_rng(3).normal(size=(64, 64))
    second = np.flipud(first)
    paths = []
    rows = []
    for index, (data, time, slot, polarization) in enumerate(
        (
            (first, "2025-01-01T00:00:00", 0, "RR"),
            (first, "2025-01-01T00:00:00", 9, "LL"),
            (second, "2025-01-01T00:01:00", 0, "LL"),
        )
    ):
        path = tmp_path / f"frame-{index}.fits"
        fits.PrimaryHDU(data=data, header=_header(time=time)).writeto(path)
        paths.append(path)
        rows.append(_raw_row(path, time=time, slot=slot, polarization=polarization))

    science_rows = analyze_radio_science_quality(rows)
    output = write_radio_science_quality_csv(tmp_path / "automatic.csv", science_rows)

    # The RR frame pairs with the same-time LL frame even though slot indexes differ.
    assert science_rows[0].polarization_correlation > 0.99
    # The same numeric slot at a different time is not used as its polarization peer.
    assert math.isnan(science_rows[2].polarization_correlation)
    text = output.read_text(encoding="utf-8")
    assert "automatic_decision" in text
    assert "negative_to_positive_tail_energy_ratio" in text


def test_group_outlier_rules_are_conservative_and_keep_legacy_bad():
    data = np.random.default_rng(17).normal(size=(64, 64))
    features, _ = compute_scientific_quality_features(
        data,
        _header(),
        expected_frequency_mhz=150.0,
        expected_time="2025-01-01T00:00:00",
    )
    cfg = RadioScienceFeatureConfig(
        bad_stripe_score=0.0,
        bad_stripe_group_z=0.0,
    )

    automatic = classify_scientific_quality(
        features,
        stripe_score_group_z=1.0,
        config=cfg,
    )
    legacy = classify_scientific_quality(
        features,
        legacy_quality_flag="bad",
        legacy_reason="p997_delta",
    )

    assert automatic.automatic_decision == "bad_candidate"
    assert legacy.automatic_decision == "bad_candidate"
    assert any("legacy_rule" in reason for reason in legacy.automatic_reasons)
