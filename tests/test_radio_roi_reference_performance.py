from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits

import solar_toolkit.radio.roi_lightcurve as roi_core
import solar_toolkit.radio.roi_lightcurve_app as app
from solar_toolkit.radio.centers import POL_LCP, POL_RCP, POL_SUM, iter_radio_images


def _header(
    *, freq_mhz: float = 149.0, date_obs: str = "2025-01-24T04:48:45"
) -> fits.Header:
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"] = 4
    header["NAXIS2"] = 4
    header["CTYPE1"] = "HPLN-TAN"
    header["CTYPE2"] = "HPLT-TAN"
    header["CUNIT1"] = "arcsec"
    header["CUNIT2"] = "arcsec"
    header["CRPIX1"] = 1.0
    header["CRPIX2"] = 1.0
    header["CRVAL1"] = 0.0
    header["CRVAL2"] = 0.0
    header["CDELT1"] = 1.0
    header["CDELT2"] = 1.0
    header["FREQ"] = float(freq_mhz)
    header["FREQUNIT"] = "MHz"
    header["DATE-OBS"] = date_obs
    header["BUNIT"] = "K"
    return header


def _write_radio_fits(
    path: Path, *, value: float = 1.0, freq_mhz: float = 149.0
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(
        data=np.full((4, 4), value, dtype=float),
        header=_header(freq_mhz=freq_mhz),
    ).writeto(path)
    return path


def _pair_rows(
    times: list[datetime],
    *,
    polarization: str,
    row_offset: int,
    freq_mhz: float = 149.0,
) -> pd.DataFrame:
    rows = []
    for index, obs_time in enumerate(times, start=1):
        row_number = row_offset + index
        rows.append(
            {
                "row": row_number,
                "path": f"C:/radio/{freq_mhz:g}MHz/{polarization}/{row_number}.fits",
                "inferred_obs_time": obs_time.isoformat(timespec="milliseconds"),
                "inferred_freq_mhz": float(freq_mhz),
                "inferred_polarization": polarization,
                "size_bytes": 4096,
                "mtime_ns": row_number,
            }
        )
    return pd.DataFrame(rows)


def _available_manifest(tmp_path: Path) -> pd.DataFrame:
    base_time = datetime(2025, 1, 24, 4, 48, 45)
    rows = []
    for row_number, freq_mhz, polarization, offset_ms in (
        (1, 149.0, POL_LCP, 0),
        (2, 149.0, POL_RCP, 100),
        (3, 238.0, POL_LCP, 10),
        (4, 238.0, POL_RCP, 110),
    ):
        path = tmp_path / f"{freq_mhz:g}MHz" / polarization / f"frame_{row_number}.fits"
        obs_time = base_time + timedelta(milliseconds=offset_ms)
        rows.append(
            {
                "row": row_number,
                "path": str(path),
                "relative_path": str(path.relative_to(tmp_path)),
                "size_bytes": 4096 + row_number,
                "mtime_ns": 10_000 + row_number,
                "size_mib": 0.004,
                "modified_time": obs_time.isoformat(timespec="seconds"),
                "inferred_freq_mhz": freq_mhz,
                "inferred_polarization": polarization,
                "inferred_obs_time": obs_time.isoformat(timespec="milliseconds"),
            }
        )
    return pd.DataFrame(rows)


def test_select_paired_rows_chooses_pair_nearest_anchor_within_tolerance():
    base_time = datetime(2025, 1, 24, 4, 48, 45)
    left_rows = _pair_rows(
        [base_time + timedelta(seconds=value) for value in (0, 10, 20)],
        polarization=POL_LCP,
        row_offset=0,
    )
    right_rows = _pair_rows(
        [
            base_time + timedelta(seconds=value, milliseconds=200)
            for value in (0, 10, 20)
        ],
        polarization=POL_RCP,
        row_offset=100,
    )

    left, right = app._select_paired_rows(
        left_rows,
        right_rows,
        anchor_time=base_time + timedelta(seconds=10, milliseconds=100),
        pair_tolerance_sec=0.5,
    )

    assert left is not None
    assert right is not None
    assert int(left["row"]) == 2
    assert int(right["row"]) == 102


def test_select_paired_rows_uses_linear_scale_time_parsing(monkeypatch):
    base_time = datetime(2025, 1, 24, 4, 48, 45)
    count = 64
    left_rows = _pair_rows(
        [base_time + timedelta(seconds=index) for index in range(count)],
        polarization=POL_LCP,
        row_offset=0,
    )
    right_rows = _pair_rows(
        [
            base_time + timedelta(seconds=index, milliseconds=100)
            for index in range(count)
        ],
        polarization=POL_RCP,
        row_offset=count,
    )
    original_row_time = app._row_time
    calls = 0

    def counted_row_time(row: pd.Series) -> datetime | None:
        nonlocal calls
        calls += 1
        return original_row_time(row)

    monkeypatch.setattr(app, "_row_time", counted_row_time)

    left, right = app._select_paired_rows(
        left_rows,
        right_rows,
        anchor_time=base_time + timedelta(seconds=32, milliseconds=50),
        pair_tolerance_sec=0.25,
    )

    assert left is not None
    assert right is not None
    assert int(left["row"]) == 33
    assert int(right["row"]) == count + 33
    assert calls <= 4 * (len(left_rows) + len(right_rows))


def test_select_paired_rows_matches_small_bruteforce_oracle():
    base_time = datetime(2025, 1, 24, 4, 48, 45)
    left_rows = _pair_rows(
        [base_time + timedelta(seconds=value) for value in (0.0, 1.1, 2.8, 5.0)],
        polarization=POL_LCP,
        row_offset=0,
    )
    right_rows = _pair_rows(
        [base_time + timedelta(seconds=value) for value in (0.2, 1.5, 3.0, 5.4)],
        polarization=POL_RCP,
        row_offset=100,
    )
    anchor = base_time + timedelta(seconds=2.4)
    tolerance = 0.5
    expected: list[tuple[float, int, int]] = []
    for left in left_rows.itertuples(index=False):
        left_time = datetime.fromisoformat(left.inferred_obs_time)
        for right in right_rows.itertuples(index=False):
            right_time = datetime.fromisoformat(right.inferred_obs_time)
            pair_delta = abs((left_time - right_time).total_seconds())
            if pair_delta <= tolerance:
                score = abs((left_time - anchor).total_seconds()) + pair_delta
                expected.append((score, int(left.row), int(right.row)))
    _, expected_left, expected_right = min(expected)

    left, right = app._select_paired_rows(
        left_rows,
        right_rows,
        anchor_time=anchor,
        pair_tolerance_sec=tolerance,
    )

    assert left is not None
    assert right is not None
    assert int(left["row"]) == expected_left
    assert int(right["row"]) == expected_right


def test_select_paired_rows_rejects_missing_or_out_of_tolerance_times():
    base_time = datetime(2025, 1, 24, 4, 48, 45)
    left_rows = _pair_rows([base_time], polarization=POL_LCP, row_offset=0)
    right_rows = _pair_rows(
        [base_time + timedelta(seconds=2)],
        polarization=POL_RCP,
        row_offset=100,
    )
    left, right = app._select_paired_rows(
        left_rows,
        right_rows,
        anchor_time=base_time,
        pair_tolerance_sec=0.5,
    )
    assert left is None
    assert right is None

    left_rows.loc[:, "inferred_obs_time"] = ""
    left, right = app._select_paired_rows(
        left_rows,
        right_rows,
        anchor_time=base_time,
        pair_tolerance_sec=5.0,
    )
    assert left is None
    assert right is None


def test_plan_reference_grid_orders_primary_first_without_fits_io(
    tmp_path, monkeypatch
):
    available = _available_manifest(tmp_path)
    loader_calls = 0

    def fail_loader(*_args, **_kwargs):
        nonlocal loader_calls
        loader_calls += 1
        pytest.fail("reference planning must not load FITS image arrays")

    monkeypatch.setattr(app, "_load_first_radio_image", fail_loader)
    monkeypatch.setattr(app, "_cached_first_radio_image", fail_loader)

    plans = app._plan_reference_grid(
        available,
        primary_frequency=238.0,
        anchor_number=1,
        preview_polarization=POL_SUM,
        pair_tolerance_sec=0.5,
    )

    assert loader_calls == 0
    assert [plan.freq_mhz for plan in plans] == pytest.approx([238.0, 149.0])
    assert [(plan.row, plan.paired_row) for plan in plans] == [(3, 4), (1, 2)]
    assert [Path(plan.path) for plan in plans] == [
        Path(available.loc[available["row"].eq(3), "path"].iloc[0]),
        Path(available.loc[available["row"].eq(1), "path"].iloc[0]),
    ]
    assert [Path(plan.paired_path) for plan in plans] == [
        Path(available.loc[available["row"].eq(4), "path"].iloc[0]),
        Path(available.loc[available["row"].eq(2), "path"].iloc[0]),
    ]
    assert all(plan.polarization == POL_SUM for plan in plans)


def test_cached_first_radio_image_is_bounded_and_uses_file_identity(
    tmp_path, monkeypatch
):
    path = _write_radio_fits(tmp_path / "149MHz" / "LL" / "frame.fits")
    stat = path.stat()
    cached_loader = app._cached_first_radio_image
    assert cached_loader.cache_parameters()["maxsize"] == 64

    original_iter = app.iter_radio_images
    read_calls = 0

    def counted_iter(*args, **kwargs):
        nonlocal read_calls
        read_calls += 1
        yield from original_iter(*args, **kwargs)

    monkeypatch.setattr(app, "iter_radio_images", counted_iter)
    cached_loader.cache_clear()
    try:
        first = cached_loader(str(path), stat.st_size, stat.st_mtime_ns)
        second = cached_loader(str(path), stat.st_size, stat.st_mtime_ns)

        assert first is second
        assert read_calls == 1
        assert cached_loader.cache_info().hits == 1
        assert cached_loader.cache_info().misses == 1

        changed_identity = cached_loader(str(path), stat.st_size, stat.st_mtime_ns + 1)

        assert changed_identity is not first
        assert read_calls == 2
        assert cached_loader.cache_info().misses == 2
    finally:
        cached_loader.cache_clear()


def test_read_only_reference_figure_omits_selection_scattergl(tmp_path):
    path = _write_radio_fits(tmp_path / "149MHz" / "LL" / "frame.fits")
    reference = next(iter_radio_images(path))

    read_only = app.build_reference_figure(
        reference,
        max_side=4,
        selection_enabled=False,
    )
    interactive = app.build_reference_figure(
        reference,
        max_side=4,
        selection_enabled=True,
    )

    assert [trace.type for trace in read_only.data] == ["heatmap"]
    assert sum(trace.type == "scattergl" for trace in interactive.data) == 1


def test_sampled_preview_coordinates_match_full_grid_with_cd_matrix(tmp_path):
    header = _header()
    header["NAXIS1"] = 10
    header["NAXIS2"] = 12
    header["CD1_1"] = -2.0
    header["CD1_2"] = 0.25
    header["CD2_1"] = -0.1
    header["CD2_2"] = 1.5
    path = tmp_path / "149MHz" / "LL" / "rotated.fits"
    path.parent.mkdir(parents=True)
    fits.PrimaryHDU(
        data=np.arange(120, dtype=float).reshape(12, 10), header=header
    ).writeto(path)
    reference = next(iter_radio_images(path))
    view, y_slice, x_slice = app._downsample_for_preview(reference.image, max_side=4)

    sampled_x, sampled_y = app._preview_coordinate_grid(
        reference,
        view.shape,
        y_slice,
        x_slice,
    )
    full_x, full_y = roi_core._pixel_center_grid_hpc_arcsec(
        reference.header,
        reference.image.shape,
    )

    assert np.allclose(sampled_x, full_x[y_slice, x_slice])
    assert np.allclose(sampled_y, full_y[y_slice, x_slice])


def test_reference_reuse_signature_tracks_request_and_file_identity(tmp_path):
    path = _write_radio_fits(tmp_path / "149MHz" / "LL" / "frame.fits")
    state = {
        "dataset_signature": "dataset-v1",
        "selection_revision": 3,
        "reference_metadata": [{"path": str(path), "paired_path": ""}],
    }
    st = SimpleNamespace(session_state=state)
    kwargs = {
        "primary_frequency": 149.0,
        "anchor_number": 1,
        "preview_polarization": POL_LCP,
        "pair_tolerance_sec": 0.5,
    }
    first = app._reference_reuse_signature(st, **kwargs)
    second = app._reference_reuse_signature(st, **kwargs)
    changed_request = app._reference_reuse_signature(
        st,
        **{**kwargs, "anchor_number": 2},
    )
    state["selection_revision"] = 4
    changed_selection = app._reference_reuse_signature(st, **kwargs)

    assert first == second
    assert changed_request != first
    assert changed_selection != first
