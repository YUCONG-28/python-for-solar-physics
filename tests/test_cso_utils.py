"""Tests for minimal CSO spectrogram reading helpers with fake HDUs."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from solar_toolkit.cso import (
    cso_base_datetime,
    normalize_cso_polarization,
    read_cso_spectrogram_hdul,
)


class FakeHDU:
    def __init__(self, header=None, data=None):
        self.header = header or {}
        self.data = data


def _fake_hdul(data, header=None, time=None, frequency=None):
    table = {
        "time": np.asarray([0.0, 1.0] if time is None else time),
        "frequency": np.asarray([100.0, 120.0] if frequency is None else frequency),
    }
    return [
        FakeHDU(
            {
                "DATE-OBS": "2025-05-03T07:15:10",
                "POLARIZA": "RCP and LCP",
                "NAXIS": np.asarray(data).ndim,
                "BUNIT": "SFU",
                **(header or {}),
            },
            np.asarray(data),
        ),
        FakeHDU(data=table),
    ]


def test_normalize_cso_polarization_for_dual_pol_cube():
    assert normalize_cso_polarization("RCP and LCP", 3) == "RL"
    assert normalize_cso_polarization("RR", 2) == "RR"


def test_cso_base_datetime_adjusts_negative_start_time():
    base = cso_base_datetime("2025-05-03T07:15:10", np.array([-0.5, 0.5]))

    assert base == dt.datetime(2025, 5, 4)


def test_read_cso_spectrogram_hdul_reads_single_2d_plane():
    hdul = _fake_hdul(np.ones((2, 2)), header={"POLARIZA": "RR", "NAXIS": 2})

    spectra = read_cso_spectrogram_hdul(hdul)

    assert len(spectra) == 1
    assert spectra[0].polar == "RR"
    assert spectra[0].unit == "SFU"
    np.testing.assert_array_equal(spectra[0].data, np.ones((2, 2)))
    np.testing.assert_array_equal(spectra[0].time, np.array([0.0, 1.0]))
    np.testing.assert_array_equal(spectra[0].freq, np.array([100.0, 120.0]))


def test_read_cso_spectrogram_hdul_splits_3d_polarizations():
    data = np.arange(8).reshape(2, 2, 2)
    hdul = _fake_hdul(data)

    spectra = read_cso_spectrogram_hdul(hdul)

    assert [spec.polar for spec in spectra] == ["RR", "LL"]
    np.testing.assert_array_equal(spectra[0].data, data[0])
    np.testing.assert_array_equal(spectra[1].data, data[1])


def test_read_cso_spectrogram_hdul_rejects_non_image_cube():
    hdul = _fake_hdul(np.ones((1, 1, 1, 1)), header={"NAXIS": 4})

    with pytest.raises(ValueError, match="2D or 3D"):
        read_cso_spectrogram_hdul(hdul)
