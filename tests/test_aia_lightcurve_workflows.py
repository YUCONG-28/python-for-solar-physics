"""Package-boundary tests for AIA light-curve workflows."""

from __future__ import annotations

import importlib
from datetime import datetime


def test_lightcurve_csv_roundtrip(tmp_path):
    from solar_toolkit.aia.lightcurve_extraction import (
        load_stored_data,
        save_processed_data,
    )

    output = tmp_path / "lightcurve.csv"
    times = [datetime(2025, 1, 24, 4, 14, 10), datetime(2025, 1, 24, 4, 14, 22)]
    fluxes = [12.5, 15.0]

    save_processed_data(times, fluxes, output)

    assert load_stored_data(output) == (times, fluxes)


def test_lightcurve_plot_helpers_keep_logarithmic_contract(tmp_path):
    from solar_toolkit.aia.lightcurve_plot import get_log10_bounds, load_single_file

    source = tmp_path / "aia.csv"
    source.write_text(
        "time,flux\n" "2025-01-24 04:14:10,0\n" "2025-01-24 04:14:22,25\n",
        encoding="utf-8",
    )

    times, fluxes, label = load_single_file(str(source))

    assert times == [datetime(2025, 1, 24, 4, 14, 22)]
    assert fluxes == [25.0]
    assert label == "aia.csv"
    assert get_log10_bounds(fluxes) == (10, 100)


def test_aia_lightcurve_and_jsoc_old_paths_are_module_aliases():
    aliases = {
        "scripts.aia_hmi.sdo_aia_lightcurve_extraction": (
            "solar_toolkit.aia.lightcurve_extraction"
        ),
        "scripts.aia_hmi.sdo_aia_lightcurve_plot": (
            "solar_toolkit.aia.lightcurve_plot"
        ),
        "scripts.aia_hmi.sdo_aia_jsoc_download_20250124": "solar_toolkit.net.jsoc",
    }

    for old_name, canonical_name in aliases.items():
        assert importlib.import_module(old_name) is importlib.import_module(
            canonical_name
        )
