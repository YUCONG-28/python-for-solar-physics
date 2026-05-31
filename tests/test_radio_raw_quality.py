from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from astropy.io import fits

from scripts.radio.legacy import radio_source_map_plot_gaussian_overlay as legacy


def _compact_source(shape: tuple[int, int] = (64, 64)) -> np.ndarray:
    y, x = np.indices(shape)
    source = 1.0e6 * np.exp(-(((x - 32) ** 2) + ((y - 32) ** 2)) / (2 * 2.4**2))
    background = 1.0e3 + 10.0 * x + 5.0 * y
    return background + source


def _striped_bad_source(shape: tuple[int, int] = (64, 64)) -> np.ndarray:
    data = _compact_source(shape)
    data[:, 6::12] += 1.5e7
    data[5::13, :] += 1.1e7
    return data


def _extended_streak_bad_source(shape: tuple[int, int] = (64, 64)) -> np.ndarray:
    data = _compact_source(shape)
    for offset in range(20):
        y = 8 + offset
        x = 24 + offset // 2
        data[y : y + 3, x : x + 4] += 1.8e7
    return data


def _write_fits(path: Path, data: np.ndarray, *, dateobs: str, freq: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    primary = fits.PrimaryHDU()
    image = fits.ImageHDU(data=data.astype(np.float32))
    image.header["DATE-OBS"] = dateobs
    image.header["FREQ"] = freq
    fits.HDUList([primary, image]).writeto(path)


def test_raw_quality_classifies_distributed_high_tail_as_bad():
    from scripts.radio.core.radio_raw_quality import (
        RawQualityThresholds,
        classify_raw_metrics,
        compute_raw_quality_metrics,
    )

    good_metrics = compute_raw_quality_metrics(_compact_source())
    bad_metrics = compute_raw_quality_metrics(_striped_bad_source())
    baseline = {"p95": good_metrics.p95, "p997": good_metrics.p997}

    result = classify_raw_metrics(bad_metrics, baseline, RawQualityThresholds())

    assert result.quality_flag == "bad"
    assert "high_tail" in result.reason
    assert "distributed_bright_pixels" in result.reason


def test_raw_quality_classifies_extended_high_tail_component_as_bad():
    from scripts.radio.core.radio_raw_quality import (
        RawQualityThresholds,
        classify_raw_metrics,
        compute_raw_quality_metrics,
    )

    shape = (192, 192)
    good_metrics = compute_raw_quality_metrics(_compact_source(shape))
    bad_metrics = compute_raw_quality_metrics(_extended_streak_bad_source(shape))
    baseline = {"p95": good_metrics.p95, "p997": good_metrics.p997}

    result = classify_raw_metrics(bad_metrics, baseline, RawQualityThresholds())

    assert result.quality_flag == "bad"
    assert "high_tail" in result.reason
    assert "extended_bright_component" in result.reason


def test_raw_quality_keeps_distributed_pixels_without_extreme_high_tail():
    from scripts.radio.core.radio_raw_quality import (
        RawQualityThresholds,
        classify_raw_metrics,
        compute_raw_quality_metrics,
    )

    good_metrics = compute_raw_quality_metrics(_compact_source())
    bad_metrics = compute_raw_quality_metrics(_striped_bad_source())
    baseline = {"p95": good_metrics.p95, "p997": good_metrics.p997}
    p95_only_metrics = replace(
        bad_metrics,
        p997=baseline["p997"] + 0.5,
    )

    result = classify_raw_metrics(
        p95_only_metrics,
        baseline,
        RawQualityThresholds(),
    )

    assert result.quality_flag == "ok"
    assert result.high_tail is True
    assert result.distributed_bright_pixels is True


def test_multi_band_slot_builder_filters_bad_fits_and_drops_incomplete_time(
    tmp_path: Path,
):
    root = tmp_path / "radio"
    good = _compact_source()
    bad = _striped_bad_source()
    for freq in (149, 164):
        for pol in ("RR", "LL"):
            for second in (0, 1):
                payload = bad if (freq, pol, second) == (149, "RR", 0) else good
                _write_fits(
                    root
                    / f"{freq}MHz"
                    / pol
                    / f"{freq}MHz_202553_07200{second}_000.fits",
                    payload,
                    dateobs=f"2025050307200{second}000",
                    freq=float(freq),
                )

    cfg = dict(legacy.DEFAULT_CONFIG)
    cfg.update(
        {
            "multi_band_root": str(root),
            "multi_band_freqs": [149, 164],
            "band_dir_pattern": "{freq}MHz/{polar}",
            "polarization": "RR+LL",
            "combine_polarizations": True,
            "rr_dir_suffix": "RR",
            "ll_dir_suffix": "LL",
            "start_idx": 0,
            "end_idx": None,
            "time_tolerance_seconds": 0.001,
            "enable_raw_quality_filter": True,
        }
    )

    slots = legacy._build_multi_band_slots(cfg)

    assert len(slots) == 1
    kept_slot = slots[0]
    assert len(kept_slot) == 2
    assert all("072001_000" in item[0] for item in kept_slot)
    assert all("072001_000" in item[1] for item in kept_slot)


def test_fixed_band_ranges_use_raw_quality_filtered_files(monkeypatch):
    rr_good = r"C:\radio\149MHz\RR\149MHz_202553_072001_000.fits"
    rr_bad = r"C:\radio\149MHz\RR\149MHz_202553_072000_000.fits"
    ll_good = r"C:\radio\149MHz\LL\149MHz_202553_072001_000.fits"
    ll_bad = r"C:\radio\149MHz\LL\149MHz_202553_072000_000.fits"

    monkeypatch.setattr(
        legacy,
        "_sorted_fits_for_band",
        lambda band_dir, start_idx, end_idx: (
            [rr_bad, rr_good] if band_dir.endswith("RR") else [ll_bad, ll_good]
        ),
    )
    monkeypatch.setattr(
        legacy,
        "_filter_bad_radio_files",
        lambda files, freq, polarization, cfg: [
            item for item in files if "072000_000" not in item
        ],
    )
    monkeypatch.setattr(
        legacy,
        "read_fits",
        lambda path: (
            np.full((2, 2), 1.0e3 if "072001_000" in path else 1.0e9),
            {},
        ),
    )
    monkeypatch.setattr(
        legacy,
        "_combine_polarization_data",
        lambda rr_data, ll_data, cfg: rr_data + ll_data,
    )

    cfg = dict(legacy.DEFAULT_CONFIG)
    cfg.update(
        {
            "multi_band_root": r"C:\radio",
            "multi_band_freqs": [149],
            "band_dir_pattern": "{freq}MHz/{polar}",
            "polarization": "RR+LL",
            "combine_polarizations": True,
            "rr_dir_suffix": "RR",
            "ll_dir_suffix": "LL",
            "start_idx": 0,
            "end_idx": None,
            "time_tolerance_seconds": 0.001,
            "enable_raw_quality_filter": True,
            "per_band_percentiles": [0, 100],
        }
    )

    band_vmins, band_vmaxs = legacy._compute_fixed_band_ranges(cfg)

    assert band_vmins == [np.log10(2.0e3)]
    assert band_vmaxs == [np.log10(2.0e3)]


def test_multi_band_time_matching_defaults_to_100ms():
    slots = legacy._build_slots_by_common_time(
        [
            ["149MHz_202553_072000_000.fits"],
            ["164MHz_202553_072000_100.fits"],
        ],
        {"date_format": "auto", "time_parsing_fallback": True},
    )

    assert slots == [
        [
            "149MHz_202553_072000_000.fits",
            "164MHz_202553_072000_100.fits",
        ]
    ]

    slots = legacy._build_slots_by_common_time(
        [
            ["149MHz_202553_072000_000.fits"],
            ["164MHz_202553_072000_101.fits"],
        ],
        {"date_format": "auto", "time_parsing_fallback": True},
    )

    assert slots == []


def test_multi_band_time_matching_uses_each_file_once():
    slots = legacy._build_slots_by_common_time(
        [
            [
                "149MHz_202553_072000_000.fits",
                "149MHz_202553_072000_050.fits",
            ],
            [
                "164MHz_202553_072000_040.fits",
                "164MHz_202553_072000_200.fits",
            ],
        ],
        {
            "date_format": "auto",
            "time_parsing_fallback": True,
            "multi_band_time_tolerance_seconds": 0.1,
        },
    )

    assert slots == [
        [
            "149MHz_202553_072000_000.fits",
            "164MHz_202553_072000_040.fits",
        ]
    ]


def test_multi_band_time_matching_rejects_slots_over_100ms_total_span():
    slots = legacy._build_slots_by_common_time(
        [
            [
                "149MHz_202553_072000_000.fits",
                "149MHz_202553_072010_000.fits",
            ],
            ["164MHz_202553_072000_050.fits"],
            [
                "190MHz_202553_072000_101.fits",
                "190MHz_202553_072010_050.fits",
            ],
        ],
        {
            "date_format": "auto",
            "time_parsing_fallback": True,
            "multi_band_time_tolerance_seconds": 0.1,
        },
    )

    assert slots == []
