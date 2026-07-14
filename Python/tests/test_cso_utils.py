"""Tests for minimal CSO spectrogram reading helpers with fake HDUs."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from solar_toolkit.radio.cso import (
    cso_base_datetime,
    normalize_cso_polarization,
    read_cso_spectrogram_hdul,
)


@pytest.mark.parametrize(
    ("right", "left", "expected"),
    [
        (10.0, 5.0, 1.0 / 3.0),
        (5.0, 10.0, -1.0 / 3.0),
        (10.0, 10.0, 0.0),
        (100.0, 1.0, 99.0 / 101.0),
        (1.0, 100.0, -99.0 / 101.0),
    ],
)
def test_cso_polarization_formula(right, left, expected):
    from solar_toolkit.radio.cso_workflow import calc_polarization_ratio

    ratio = calc_polarization_ratio(
        np.asarray([right], dtype=np.float32),
        np.asarray([left], dtype=np.float32),
    )[0]

    assert float(ratio) == pytest.approx(expected, abs=1e-6)


def test_cso_help_has_no_science_self_test_side_effect(capsys):
    from solar_toolkit.radio import cso_workflow

    with pytest.raises(SystemExit) as exc_info:
        cso_workflow.main(["--help"])

    assert exc_info.value.code == 0
    assert "Testing Polarization Ratio Formula" not in capsys.readouterr().out


def test_cso_cli_applies_independent_workspace_overrides(tmp_path):
    from solar_toolkit.radio import cso_workflow

    output_dir = tmp_path / "spectrogram"
    args = cso_workflow.build_parser().parse_args(
        [
            "--file-path",
            str(tmp_path / "input.fits"),
            "--time-start",
            "2025-05-03T07:15:10",
            "--time-end",
            "2025-05-03T07:16:10",
            "--frequency-start",
            "90",
            "--frequency-end",
            "180",
            "--output-dir",
            str(output_dir),
            "--rebin-time",
            "800",
            "--rebin-frequency",
            "120",
            "--max-workers",
            "3",
            "--plot-ll",
            "--plot-rr",
            "--no-plot-sum",
            "--no-plot-ratio",
        ]
    )
    cfg = cso_workflow.PlotConfig()

    cso_workflow._apply_cli_overrides(cfg, args)

    assert cfg.file_path == str(tmp_path / "input.fits")
    assert cfg.t_start == dt.datetime(2025, 5, 3, 7, 15, 10)
    assert cfg.t_end == dt.datetime(2025, 5, 3, 7, 16, 10)
    assert cfg.f_start == 90.0
    assert cfg.f_end == 180.0
    assert cfg.save_path == str(output_dir)
    assert cfg.rebin_t_target == 800
    assert cfg.rebin_f_target == 120
    assert cfg.max_workers == 3
    assert cfg.plot_ll is True
    assert cfg.plot_rr is True
    assert cfg.plot_sum is False
    assert cfg.plot_ratio is False


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
