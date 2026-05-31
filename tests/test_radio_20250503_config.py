from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from scripts.radio.configs import (
    load_drift_selection_product_config,
    load_newkirk_height_comparison_config,
    load_radio_config_module,
    load_radio_diagnostic_presentation_config,
    load_radio_user_config,
)
from scripts.radio.core.radio_coordinates import normalize_roi_bounds_arcsec
from scripts.radio.core.radio_gaussian_fit import _gaussian_quality_config


def test_20250503_config_is_independent_from_20250124_config():
    config_source = Path("scripts/radio/configs/radio_20250503_config.py").read_text(
        encoding="utf-8"
    )

    assert "radio_20250124_config" not in config_source
    assert "_BASE_EVENT_CONFIG" not in config_source
    assert "copy.deepcopy" not in config_source


def test_20250503_config_has_real_event_paths_and_full_event_sections():
    module = load_radio_config_module("radio_20250503_config")
    user_config, newkirk_config = load_radio_user_config("radio_20250503_config")
    height_config = load_newkirk_height_comparison_config("radio_20250503_config")
    drift_product_config = load_drift_selection_product_config("radio_20250503_config")
    presentation_config = load_radio_diagnostic_presentation_config(
        "radio_20250503_config"
    )
    assert set(module.EVENT_CONFIG) >= {
        "user",
        "output",
        "newkirk",
        "newkirk_height_comparison",
        "drift_selection_products",
        "diagnostic_presentation",
    }
    assert "newkirk_spatial" not in module.EVENT_CONFIG
    assert user_config == module.EVENT_CONFIG["user"]
    assert module.OUTPUT_CONFIG == module.EVENT_CONFIG["output"]
    assert newkirk_config["solar_radius_arcsec"] == 959.63
    assert (
        height_config["output_table_name"]
        == "gaussian_newkirk_height_comparison_table.csv"
    )
    assert drift_product_config["output_subdir"] == "drift_selection"
    assert presentation_config["comparison_frequency_mhz"] == [
        149,
        164,
        190,
        205,
        223,
        238,
    ]

    assert not _contains_todo(module.EVENT_CONFIG)
    assert user_config["data"]["multi_band_freqs"] == [149, 164, 190, 205, 223, 238]
    assert user_config["data"]["multi_band_root"] == (
        r"D:\spike_topping_type_III\2025\20250503\20250503UT071600-072600"
    )
    assert user_config["data"]["single_file_path"] == (
        r"D:\spike_topping_type_III\2025\20250503\20250503UT071600-072600"
        r"\149MHz\RR\149MHz_202553_071600_353.fits"
    )
    assert user_config["data"]["data_dir"] == (
        r"D:\spike_topping_type_III\2025\20250503\20250503UT071600-072600\149MHz\RR"
    )
    assert user_config["data"]["start_idx"] == 648
    assert user_config["data"]["end_idx"] == 944
    assert user_config["data"]["multi_band_time_tolerance_seconds"] == 0.1
    assert user_config["features"]["raw_quality_filter"] is True
    gaussian = user_config["gaussian"]
    assert gaussian["gaussian_source_mode"] == "multi"
    assert gaussian["multi_gaussian_source_count"] is None
    assert gaussian["multi_gaussian_max_sources"] == 2
    assert gaussian["multi_gaussian_min_peak_fraction"] == 0.16
    assert gaussian["multi_gaussian_min_peak_distance_pixels"] == 2
    assert gaussian["fit_min_mask_pixels"] == 8
    assert (
        gaussian["gaussian_per_band_params"][149][
            "gaussian_max_center_peak_distance_fraction_of_fwhm"
        ]
        == 0.65
    )
    assert gaussian["gaussian_per_band_params"][164]["max_fwhm_arcsec"] == 400.0
    assert (
        gaussian["gaussian_per_band_params"][190][
            "multi_gaussian_min_peak_distance_pixels"
        ]
        == 1
    )
    assert (
        gaussian["gaussian_per_band_params"][238]["multi_gaussian_min_peak_fraction"]
        == 0.10
    )
    assert user_config["spectrogram"]["file_paths"] == [
        r"D:\spike_topping_type_III\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503071510_V01.01.fits",
        r"D:\spike_topping_type_III\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503072013_V01.01.fits",
    ]
    assert user_config["spectrogram"]["file_path"] == (
        r"D:\spike_topping_type_III\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503071510_V01.01.fits"
    )
    assert user_config["spectrogram"]["time_start"] == "2025-05-03T07:20:25"
    assert user_config["spectrogram"]["time_end"] == "2025-05-03T07:22:25"
    assert user_config["output"]["output_dir"] == module.OUTPUT_CONFIG["output_dir"]
    assert module.OUTPUT_CONFIG["output_dir"] == (
        r"D:\spike_topping_type_III\2025\20250503\output"
    )


def test_radio_event_configs_expose_central_output_config_without_spatial():
    for config_name in ("radio_20250124_config", "radio_20250503_config"):
        module = load_radio_config_module(config_name)
        user_config, newkirk_config = load_radio_user_config(config_name)

        assert "newkirk_spatial" not in module.EVENT_CONFIG
        assert hasattr(module, "OUTPUT_CONFIG")
        assert user_config["output"]["output_dir"] == module.OUTPUT_CONFIG["output_dir"]
        assert newkirk_config["output_csv"] == module.OUTPUT_CONFIG["newkirk_csv"]
        assert (
            newkirk_config["drift_speed_csv"] == module.OUTPUT_CONFIG["drift_speed_csv"]
        )


def test_radio_event_configs_expose_event_specific_spectrogram_display_range():
    expected_ranges = {
        "radio_20250124_config": (2.5, 4.5),
        "radio_20250503_config": (1.9, 3.6),
    }
    for config_name, (expected_vmin, expected_vmax) in expected_ranges.items():
        user_config, _newkirk_config = load_radio_user_config(config_name)
        spectrogram = user_config["spectrogram"]

        assert spectrogram["vmin"] == expected_vmin
        assert spectrogram["vmax"] == expected_vmax
        assert spectrogram["use_log10"] is True
        assert spectrogram["cmap"] == "jet"


def test_legacy_build_config_maps_nested_spectrogram_display_range():
    legacy = _import_legacy_source_map_with_optional_stubs()

    cfg = legacy.build_config(
        {
            "spectrogram": {
                "vmin": 2.1,
                "vmax": 4.9,
                "use_log10": False,
                "cmap": "magma",
                "colorbar_label": "raw intensity",
            }
        },
        {},
    )

    assert cfg["spectrogram_vmin"] == 2.1
    assert cfg["spectrogram_vmax"] == 4.9
    assert cfg["spectrogram_use_log10"] is False
    assert cfg["spectrogram_cmap"] == "magma"
    assert cfg["spectrogram_colorbar_label"] == "raw intensity"


def test_legacy_build_config_maps_raw_quality_filter():
    legacy = _import_legacy_source_map_with_optional_stubs()

    cfg = legacy.build_config(
        {
            "features": {"raw_quality_filter": True},
            "raw_quality": {"filter_bad_fits": True},
        },
        legacy.DEFAULT_CONFIG,
    )

    assert cfg["enable_raw_quality_filter"] is True


def test_legacy_build_config_maps_multi_source_gaussian_tuning():
    legacy = _import_legacy_source_map_with_optional_stubs()

    cfg = legacy.build_config(
        {
            "gaussian": {
                "gaussian_source_mode": "multi",
                "multi_gaussian_source_count": None,
                "multi_gaussian_max_sources": 2,
                "multi_gaussian_min_peak_fraction": 0.16,
                "multi_gaussian_min_peak_distance_pixels": 2,
                "fit_min_mask_pixels": 8,
                "gaussian_per_band_params": {
                    149: {"gaussian_max_center_peak_distance_fraction_of_fwhm": 0.65},
                    164: {"max_fwhm_arcsec": 400.0},
                    190: {"multi_gaussian_min_peak_distance_pixels": 1},
                    238: {"multi_gaussian_min_peak_fraction": 0.10},
                },
            }
        },
        legacy.DEFAULT_CONFIG,
    )

    assert cfg["gaussian_source_mode"] == "multi"
    assert cfg["multi_gaussian_source_count"] is None
    assert cfg["multi_gaussian_max_sources"] == 2
    assert cfg["multi_gaussian_min_peak_fraction"] == 0.16
    assert cfg["multi_gaussian_min_peak_distance_pixels"] == 2
    assert cfg["fit_min_mask_pixels"] == 8
    cfg_149 = legacy.config_for_gaussian_band(cfg, 149)
    cfg_164 = legacy.config_for_gaussian_band(cfg, 164)
    cfg_190 = legacy.config_for_gaussian_band(cfg, 190)
    cfg_238 = legacy.config_for_gaussian_band(cfg, 238)
    assert cfg_149["gaussian_max_center_peak_distance_fraction_of_fwhm"] == 0.65
    assert cfg_164["max_fwhm_arcsec"] == 400.0
    assert _gaussian_quality_config(cfg_164)["max_fwhm_arcsec"] == 400.0
    assert cfg_190["multi_gaussian_min_peak_distance_pixels"] == 1
    assert cfg_238["multi_gaussian_min_peak_fraction"] == 0.10


def test_aia_radio_hmi_roi_uses_explicit_bounds_with_legacy_fallback():
    expected = {
        "radio_20250124_config": {
            "left": 600.0,
            "bottom": -800.0,
            "right": 1600.0,
            "top": 200.0,
        },
        "radio_20250503_config": {
            "left": -800.0,
            "bottom": -200.0,
            "right": 0.0,
            "top": 400.0,
        },
    }

    for config_name, expected_bounds in expected.items():
        module = load_radio_config_module(config_name)
        wcs_config = module.AIA_RADIO_HMI_CONFIG["wcs_reproject"]

        assert "roi_bounds_arcsec" in wcs_config
        assert "roi_bottom_left" not in wcs_config
        assert "roi_top_right" not in wcs_config
        assert normalize_roi_bounds_arcsec(wcs_config) == expected_bounds

    legacy_bounds = normalize_roi_bounds_arcsec(
        {
            "roi_bottom_left": [-800, -200],
            "roi_top_right": [0, 400],
        }
    )
    assert legacy_bounds == {
        "left": -800.0,
        "bottom": -200.0,
        "right": 0.0,
        "top": 400.0,
    }


def test_aia_radio_hmi_roi_rejects_inverted_bounds():
    try:
        normalize_roi_bounds_arcsec(
            {"roi_bounds_arcsec": {"left": 1, "right": 0, "bottom": -1, "top": 1}}
        )
    except ValueError as exc:
        assert "left < right" in str(exc)
    else:
        raise AssertionError("Expected inverted ROI bounds to raise ValueError")


def _contains_todo(value):
    if isinstance(value, str):
        return "TODO:" in value
    if isinstance(value, dict):
        return any(_contains_todo(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_todo(item) for item in value)
    return False


def _import_legacy_source_map_with_optional_stubs():
    module_name = "scripts.radio.legacy.radio_source_map_plot_gaussian_overlay"
    if module_name in sys.modules:
        return sys.modules[module_name]

    scipy = types.ModuleType("scipy")
    scipy_ndimage = types.ModuleType("scipy.ndimage")
    scipy_optimize = types.ModuleType("scipy.optimize")
    tqdm_module = types.ModuleType("tqdm")
    for name in ("binary_dilation", "find_objects", "label", "median_filter"):
        setattr(scipy_ndimage, name, lambda *args, **kwargs: None)
    scipy_optimize.curve_fit = lambda *args, **kwargs: None
    tqdm_module.tqdm = lambda iterable=None, *args, **kwargs: iterable
    stubs = {
        "scipy": scipy,
        "scipy.ndimage": scipy_ndimage,
        "scipy.optimize": scipy_optimize,
        "tqdm": tqdm_module,
    }
    created = []
    for name, module in stubs.items():
        if name not in sys.modules and not _module_available(name):
            sys.modules[name] = module
            created.append(name)
    try:
        return importlib.import_module(module_name)
    finally:
        for name in reversed(created):
            sys.modules.pop(name, None)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False
