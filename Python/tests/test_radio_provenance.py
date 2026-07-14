from __future__ import annotations

import json


def test_radio_provenance_records_science_assumptions(tmp_path):
    from solar_toolkit.radio.provenance import write_radio_provenance

    path = write_radio_provenance(
        tmp_path,
        {
            "roi_bounds_arcsec": {"left": -10, "right": 20},
            "gaussian": {
                "fit_snr_threshold": 5.0,
                "fit_background_model": "constant",
            },
            "preserve_fits_wcs_orientation": True,
        },
        newkirk_config={"multipliers": [1, 2, 4], "harmonics": [1, 2]},
        config_source="event_config",
        cli_overrides={"output_dir": str(tmp_path), "unused": None},
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["config_source"] == "event_config"
    assert payload["science"]["roi"]["roi_bounds_arcsec"]["left"] == -10
    assert payload["science"]["thresholds"]["gaussian.fit_snr_threshold"] == 5.0
    assert payload["science"]["gaussian"]["gaussian.fit_background_model"] == (
        "constant"
    )
    assert payload["science"]["newkirk"]["harmonics"] == [1, 2]
    assert payload["precedence"][0] == "CLI arguments"


def test_provenance_output_resolution_requires_explicit_output():
    from solar_toolkit.radio.provenance import resolve_provenance_output_dir

    assert resolve_provenance_output_dir({}) is None
    assert (
        resolve_provenance_output_dir(
            {"output": {"output_dir": "products", "analysis_subdir": "radio"}}
        ).as_posix()
        == "products/radio"
    )
