from __future__ import annotations

from scripts.radio.configs import load_radio_output_config, load_radio_user_config

FREQUENCIES_9_BAND = [149, 164, 190, 223, 238, 285, 300, 324, 309]


def test_20250124_9band_preview_configs_are_gated_by_polarization():
    expected = {
        "radio_20250124_center_pm2min_9band_raw_ll_preview_config": {
            "polarization": "LL",
            "combine": False,
            "analysis_subdir": "radio_source_maps_9band_preview_LL",
        },
        "radio_20250124_center_pm2min_9band_raw_rr_preview_config": {
            "polarization": "RR",
            "combine": False,
            "analysis_subdir": "radio_source_maps_9band_preview_RR",
        },
        "radio_20250124_center_pm2min_9band_raw_rrll_preview_config": {
            "polarization": "RR+LL",
            "combine": True,
            "analysis_subdir": "radio_source_maps_9band_preview_RR_LL",
        },
    }

    for config_name, case in expected.items():
        user_config, _newkirk_config = load_radio_user_config(config_name)
        output_config = load_radio_output_config(config_name)

        assert user_config["data"]["multi_band_freqs"] == FREQUENCIES_9_BAND
        assert user_config["data"]["start_idx"] == 1588
        assert user_config["data"]["end_idx"] == 1589
        assert user_config["data"]["polarization"] == case["polarization"]
        assert user_config["data"]["combine_polarizations"] is case["combine"]
        assert user_config["data"]["multi_band_layout"] == (3, 3)
        assert user_config["data"]["multi_band_time_tolerance_seconds"] == 0.3
        assert user_config["features"]["gaussian_overlay"] is False
        assert user_config["features"]["save_gaussian_diagnostics"] is False
        assert user_config["features"]["spectrogram_panel"] is False
        assert user_config["drift_rate"]["enabled"] is False
        assert output_config["analysis_subdir"] == case["analysis_subdir"]


def test_20250124_9band_full_configs_use_full_centered_window():
    expected = {
        "radio_20250124_center_pm2min_9band_raw_ll_full_config": {
            "polarization": "LL",
            "combine": False,
            "analysis_subdir": "radio_source_maps_9band_full_LL",
        },
        "radio_20250124_center_pm2min_9band_raw_rr_full_config": {
            "polarization": "RR",
            "combine": False,
            "analysis_subdir": "radio_source_maps_9band_full_RR",
        },
        "radio_20250124_center_pm2min_9band_raw_rrll_full_config": {
            "polarization": "RR+LL",
            "combine": True,
            "analysis_subdir": "radio_source_maps_9band_full_RR_LL",
        },
    }

    for config_name, case in expected.items():
        user_config, _newkirk_config = load_radio_user_config(config_name)
        output_config = load_radio_output_config(config_name)

        assert user_config["data"]["multi_band_freqs"] == FREQUENCIES_9_BAND
        assert user_config["data"]["start_idx"] == 1333
        assert user_config["data"]["end_idx"] == 1919
        assert user_config["data"]["polarization"] == case["polarization"]
        assert user_config["data"]["combine_polarizations"] is case["combine"]
        assert user_config["data"]["multi_band_layout"] == (3, 3)
        assert user_config["data"]["multi_band_time_tolerance_seconds"] == 0.3
        assert user_config["features"]["gaussian_overlay"] is False
        assert user_config["features"]["save_gaussian_diagnostics"] is False
        assert user_config["features"]["spectrogram_panel"] is False
        assert user_config["drift_rate"]["enabled"] is False
        assert output_config["analysis_subdir"] == case["analysis_subdir"]
