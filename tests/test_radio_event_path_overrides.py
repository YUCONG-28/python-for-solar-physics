from __future__ import annotations

import copy
import importlib

import pytest
import yaml

from solar_toolkit.radio.configs._path_overrides import apply_event_path_overrides


@pytest.mark.parametrize(
    ("module_name", "script_key"),
    [
        (
            "solar_toolkit.radio.configs.radio_20250124_config",
            "radio_20250124_config",
        ),
        (
            "solar_toolkit.radio.configs.radio_20250503_config",
            "radio_20250503_config",
        ),
    ],
)
def test_event_config_accepts_only_local_path_overrides(
    tmp_path, monkeypatch, module_name, script_key
):
    config_path = tmp_path / "paths.local.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "scripts": {
                    script_key: {
                        "user": {
                            "data": {"multi_band_root": "private/radio"},
                            "spectrogram": {"file_path": "private/spectrum.fits"},
                        },
                        "output": {"output_dir": "private/output"},
                        "aia_radio_hmi": {"paths": {"aia_base_dir": "private/aia"}},
                    }
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOLAR_PHYSICS_CONFIG", str(config_path))

    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    try:
        assert module.USER_CONFIG["data"]["multi_band_root"] == "private/radio"
        assert module.USER_CONFIG["spectrogram"]["file_path"] == (
            "private/spectrum.fits"
        )
        assert module.OUTPUT_CONFIG["output_dir"] == "private/output"
        assert module.AIA_RADIO_HMI_CONFIG["paths"]["aia_base_dir"] == "private/aia"
        assert module.USER_CONFIG["gaussian"]["fit_snr_threshold"] == 5.0
    finally:
        monkeypatch.delenv("SOLAR_PHYSICS_CONFIG")
        importlib.reload(module)


def test_event_config_rejects_scientific_parameter_overrides(monkeypatch):
    event_config = {"user": {"gaussian": {"fit_snr_threshold": 5.0}}}
    monkeypatch.setattr(
        "solar_toolkit.radio.configs._path_overrides.load_script_config",
        lambda *_args, **_kwargs: {"user": {"gaussian": {"fit_snr_threshold": 1.0}}},
    )

    with pytest.raises(ValueError, match="Only path fields"):
        apply_event_path_overrides(copy.deepcopy(event_config), "radio_test_config")
