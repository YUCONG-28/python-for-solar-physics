from __future__ import annotations

from pathlib import Path

from scripts.radio.configs import (
    load_drift_selection_product_config,
    load_newkirk_height_comparison_config,
    load_newkirk_spatial_config,
    load_radio_config_module,
    load_radio_diagnostic_presentation_config,
    load_radio_user_config,
)


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
    spatial_config = load_newkirk_spatial_config("radio_20250503_config")

    assert set(module.EVENT_CONFIG) >= {
        "user",
        "newkirk",
        "newkirk_height_comparison",
        "drift_selection_products",
        "diagnostic_presentation",
        "newkirk_spatial",
    }
    assert user_config == module.EVENT_CONFIG["user"]
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
    assert spatial_config["enable"] is False

    assert not _contains_todo(module.EVENT_CONFIG)
    assert user_config["data"]["multi_band_freqs"] == [149, 164, 190, 205, 223, 238]
    assert user_config["data"]["multi_band_root"] == (
        r"<PROJECT_ROOT>\2025\20250503\20250503UT071600-072600"
    )
    assert user_config["data"]["single_file_path"] == (
        r"<PROJECT_ROOT>\2025\20250503\20250503UT071600-072600"
        r"\149MHz\RR\149MHz_202553_071600_353.fits"
    )
    assert user_config["data"]["data_dir"] == (
        r"<PROJECT_ROOT>\2025\20250503\20250503UT071600-072600\149MHz\RR"
    )
    assert user_config["data"]["start_idx"] == 0
    assert user_config["data"]["end_idx"] == 1467
    assert user_config["spectrogram"]["file_paths"] == [
        r"<PROJECT_ROOT>\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503071510_V01.01.fits",
        r"<PROJECT_ROOT>\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503072013_V01.01.fits",
    ]
    assert user_config["spectrogram"]["file_path"] == (
        r"<PROJECT_ROOT>\2025\20250503\OROCH_MWRS01_SRSP_L1_05M_20250503071510_V01.01.fits"
    )
    assert user_config["spectrogram"]["time_start"] == "2025-05-03T07:20:25"
    assert user_config["spectrogram"]["time_end"] == "2025-05-03T07:22:25"
    assert user_config["output"]["output_dir"] == (
        r"<PROJECT_ROOT>\2025\20250503\RS_test"
    )
    assert spatial_config["aia171_path"] == (
        r"<PROJECT_ROOT>\2025\20250503\AIA\171"
        r"\aia.lev1_euv_12s.2025-05-03T071558Z.171.image_lev1.fits"
    )


def _contains_todo(value):
    if isinstance(value, str):
        return "TODO:" in value
    if isinstance(value, dict):
        return any(_contains_todo(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_todo(item) for item in value)
    return False
