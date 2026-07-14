"""Regression tests for package-owned X-ray/DEM workflows."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import savgol_filter

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_savgol_modes_preserve_both_historical_window_policies():
    from scripts.xray_dem.neupert_sxr_derivative_hxr_comparison import (
        smooth_flux_data as legacy_neupert_smooth,
    )
    from solar_toolkit.xray_dem.processing import smooth_flux_data

    values = np.linspace(0.0, 2.0, 31) ** 2 + np.sin(np.arange(31)) * 0.01

    direct_even = smooth_flux_data(values, 22, 3, method="savgol")
    adjusted_odd = legacy_neupert_smooth(values, 22, 3)

    assert np.array_equal(direct_even, savgol_filter(values, 22, 3))
    assert np.array_equal(adjusted_odd, savgol_filter(values, 23, 3))


def test_derivative_modes_preserve_gradient_and_forward_difference():
    from solar_toolkit.xray_dem.processing import calculate_derivative

    times = np.asarray(
        [
            "2024-08-08T19:00:00",
            "2024-08-08T19:00:02",
            "2024-08-08T19:00:05",
        ],
        dtype="datetime64[s]",
    )
    flux = np.asarray([1.0, 5.0, 14.0])
    seconds = times.astype("datetime64[ns]").astype(np.int64) / 1_000_000_000

    assert np.array_equal(
        calculate_derivative(times, flux, method="forward"),
        np.diff(flux) / np.diff(seconds),
    )
    assert np.array_equal(
        calculate_derivative(times, flux, method="gradient"),
        np.gradient(flux, seconds),
    )
    assert np.array_equal(
        calculate_derivative(times.astype(str), flux, method="forward"),
        np.diff(flux) / np.diff(seconds),
    )


def test_netcdf_loader_crops_and_detaches_source(tmp_path):
    xr = pytest.importorskip("xarray")
    from solar_toolkit.xray_dem import load_sxr_data
    from solar_toolkit.xray_dem.sxr import load_goes_sxr_dataset

    path = tmp_path / "goes.nc"
    times = np.asarray(
        [
            "2024-08-08T19:00:00",
            "2024-08-08T19:01:00",
            "2024-08-08T19:02:00",
        ],
        dtype="datetime64[s]",
    )
    xr.Dataset(
        {
            "xrsa_flux": ("time", [1.0, 2.0, 3.0]),
            "xrsb_flux": ("time", [4.0, 5.0, 6.0]),
        },
        coords={"time": times},
    ).to_netcdf(path)

    loaded = load_goes_sxr_dataset(path, "2024-08-08T19:01:00", "2024-08-08T19:02:00")
    dispatched = load_sxr_data(path, "2024-08-08T19:01:00", "2024-08-08T19:02:00")

    assert loaded.sizes["time"] == 2
    assert loaded["xrsa_flux"].values.tolist() == [2.0, 3.0]
    assert dispatched["xrsb_flux"].values.tolist() == [5.0, 6.0]
    path.unlink()
    assert loaded["xrsa_flux"].values.tolist() == [2.0, 3.0]


def test_hxi_loader_preserves_energy_channels_and_inclusive_crop(tmp_path):
    from astropy.io import fits

    from solar_toolkit.xray_dem.hxi import load_hxi_lightcurve

    path = tmp_path / "hxi.fits"
    time_hdu = fits.BinTableHDU.from_columns(
        [fits.Column(name="TIME", format="D", array=np.asarray([0.0, 60.0, 120.0]))]
    )
    counts = np.arange(12.0).reshape(3, 4)
    count_hdu = fits.BinTableHDU.from_columns(
        [fits.Column(name="CTS_THINTHICK", format="4D", array=counts)]
    )
    fits.HDUList([fits.PrimaryHDU(), time_hdu, fits.BinTableHDU(), count_hdu]).writeto(
        path
    )

    loaded = load_hxi_lightcurve(
        path,
        datetime(2018, 12, 31, 16, 1),
        datetime(2018, 12, 31, 16, 2),
    )

    assert len(loaded["times"]) == 2
    assert loaded["data"]["10-20 keV"].tolist() == [4.0, 8.0]
    assert loaded["data"]["100-300 keV"].tolist() == [7.0, 11.0]


@pytest.mark.parametrize(
    ("script", "entrypoint"),
    [
        ("goes_sxr_lightcurve_plot.py", "goes_lightcurve_main"),
        ("neupert_timing_error_analysis.py", "neupert_timing_main"),
        (
            "neupert_sxr_derivative_hxr_comparison.py",
            "neupert_comparison_main",
        ),
        ("flare_aia_sxr_hxr_summary_plot.py", "flare_summary_main"),
    ],
)
def test_repository_scripts_are_thin_cli_facades(script, entrypoint):
    cli = importlib.import_module("solar_toolkit.xray_dem.cli")
    module = importlib.import_module(f"scripts.xray_dem.{script.removesuffix('.py')}")

    assert module.main is getattr(cli, entrypoint)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "xray_dem" / script), "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_xray_script_imports_do_not_load_plotting_or_data_backends():
    code = """
import importlib
import sys
for name in [
    'scripts.xray_dem.goes_sxr_lightcurve_plot',
    'scripts.xray_dem.neupert_timing_error_analysis',
    'scripts.xray_dem.neupert_sxr_derivative_hxr_comparison',
    'scripts.xray_dem.flare_aia_sxr_hxr_summary_plot',
]:
    importlib.import_module(name)
assert 'matplotlib.pyplot' not in sys.modules
assert 'xarray' not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
