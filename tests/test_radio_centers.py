from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

from solar_toolkit.radio.centers import (
    POL_LCP,
    POL_RCP,
    POL_SUM,
    compute_source_center,
    extract_radio_centers,
    infer_polarization,
    parse_frequency_mhz,
)


def _linear_header(**updates) -> fits.Header:
    header = fits.Header()
    header["CRPIX1"] = 1.0
    header["CRPIX2"] = 1.0
    header["CRVAL1"] = 0.0
    header["CRVAL2"] = 0.0
    header["CDELT1"] = 2.0
    header["CDELT2"] = 3.0
    header["CUNIT1"] = "arcsec"
    header["CUNIT2"] = "arcsec"
    for key, value in updates.items():
        header[key] = value
    return header


def test_infers_frequency_and_polarization_from_header_and_filename():
    header = fits.Header()
    header["FREQ"] = 149_000_000.0
    header["FREQUNIT"] = "Hz"
    header["POLAR"] = "StokesI"

    assert parse_frequency_mhz(Path("radio_image.fits"), header) == pytest.approx(149.0)
    assert infer_polarization(Path("radio_image.fits"), header) == POL_SUM

    assert infer_polarization(Path("source_RCP_164MHz.fits"), fits.Header()) == POL_RCP


def test_computes_95_percent_bg_peak_geometric_center_in_arcsec():
    image = np.zeros((5, 5), dtype=float)
    image[1, 2] = 10.0
    image[1, 3] = 10.0

    center = compute_source_center(
        image,
        _linear_header(),
        threshold_frac=0.95,
        threshold_mode="bg_peak",
        centroid="geometric",
    )

    assert center["center_x_pix"] == pytest.approx(2.5)
    assert center["center_y_pix"] == pytest.approx(1.0)
    assert center["center_x_arcsec"] == pytest.approx(5.0)
    assert center["center_y_arcsec"] == pytest.approx(3.0)
    assert center["area_pix"] == 2
    assert center["threshold_value"] == pytest.approx(9.5)


def test_extracts_radio_centers_and_builds_lcp_rcp_sum(tmp_path):
    obs_time = "2025-01-24T04:48:37.681"
    for pol, peak_x in [(POL_LCP, 1), (POL_RCP, 3)]:
        image = np.zeros((5, 5), dtype=float)
        image[2, peak_x] = 10.0
        header = _linear_header(FREQ=149.0, FREQUNIT="MHz", POLAR=pol)
        header["DATE-OBS"] = obs_time
        fits.writeto(tmp_path / f"149MHz_{pol}.fits", image, header, overwrite=True)

    out = tmp_path / "radio_centers.csv"
    df = extract_radio_centers(
        tmp_path,
        out=out,
        threshold_frac=0.95,
        threshold_mode="bg_peak",
        centroid="geometric",
        make_sum=True,
    )

    assert out.exists()
    written = pd.read_csv(out)
    assert len(df) == len(written) == 3
    assert {POL_LCP, POL_RCP, POL_SUM} <= set(df["polarization"])
    assert set(df["quality_flag"]) == {"ok"}

    sum_row = df[df["polarization"] == POL_SUM].iloc[0]
    assert sum_row["source_label"] == "paired_L_plus_R"
    assert sum_row["freq_mhz"] == pytest.approx(149.0)
    assert sum_row["center_method"].startswith("threshold_geometric_bg_peak")
