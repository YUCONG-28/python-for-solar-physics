from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits
from matplotlib.path import Path as MplPath

import solar_toolkit.radio.roi_lightcurve as roi_core
import solar_toolkit.radio.roi_lightcurve_app as app
from solar_toolkit.radio.centers import POL_LCP, POL_RCP, POL_SUM


def _header(
    *,
    freq_mhz: float = 149.0,
    date_obs: str = "2025-01-24T04:48:45",
    shape: tuple[int, int] = (8, 9),
) -> fits.Header:
    header = fits.Header()
    header["NAXIS"] = 2
    header["NAXIS1"] = int(shape[1])
    header["NAXIS2"] = int(shape[0])
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


def _write_fits(path: Path, data: np.ndarray, header: fits.Header) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fits.PrimaryHDU(data=np.asarray(data, dtype=np.float64), header=header).writeto(path)
    return path


def _meta(
    name: str,
    *,
    polarization: str,
    seconds: float | None,
    freq_mhz: float = 149.0,
    shape: tuple[int, int] = (8, 9),
    bunit: str = "K",
) -> roi_core._RadioImageMeta:
    base = datetime(2025, 1, 24, 4, 48, 45)
    obs_time = None if seconds is None else base + timedelta(seconds=seconds)
    header = _header(
        freq_mhz=freq_mhz,
        date_obs=(obs_time or base).isoformat(timespec="milliseconds"),
        shape=shape,
    )
    header["BUNIT"] = bunit
    return roi_core._RadioImageMeta(
        path=Path(f"C:/radio/{freq_mhz:g}MHz/{polarization}/{name}.fits"),
        hdu_index=0,
        image_index=0,
        image_shape=shape,
        header=header,
        pol=polarization,
        freq_mhz=freq_mhz,
        obs_time=obs_time,
    )


def _bruteforce_pairing_oracle(metas, tolerance_sec):
    left_items = [
        item
        for item in metas
        if item.pol == POL_LCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    right_items = [
        item
        for item in metas
        if item.pol == POL_RCP
        and item.obs_time is not None
        and np.isfinite(item.freq_mhz)
    ]
    paired = []
    skipped = []
    used_right = set()
    for left in left_items:
        candidate_index = None
        candidate_dt = None
        for index, right in enumerate(right_items):
            if index in used_right or not roi_core._same_frequency(
                left.freq_mhz, right.freq_mhz
            ):
                continue
            dt = abs((left.obs_time - right.obs_time).total_seconds())
            if dt <= tolerance_sec and (candidate_dt is None or dt < candidate_dt):
                candidate_index = index
                candidate_dt = dt
        if candidate_index is None:
            skipped.append((left, "unmatched_pair", ""))
            continue
        right = right_items[candidate_index]
        detail = roi_core._metadata_pair_incompatibility(left, right)
        if detail:
            skipped.append((left, "mismatched_pair", str(right.path)))
            continue
        used_right.add(candidate_index)
        paired.append((left, right))
    for index, right in enumerate(right_items):
        if index not in used_right:
            skipped.append((right, "unmatched_pair", ""))
    return paired, skipped


def _paired_paths(plan):
    return [(str(left.path), str(right.path)) for left, right in plan.paired]


def _skipped_identity(plan):
    return [
        (str(meta.path), flag, paired_path)
        for meta, flag, _detail, paired_path in plan.skipped
    ]


@pytest.mark.parametrize(
    "metas",
    [
        pytest.param(
            [
                _meta("l-boundary", polarization=POL_LCP, seconds=0.0),
                _meta("r-boundary", polarization=POL_RCP, seconds=0.5),
            ],
            id="tolerance-boundary",
        ),
        pytest.param(
            [
                _meta("l-outside", polarization=POL_LCP, seconds=0.0),
                _meta("r-outside", polarization=POL_RCP, seconds=0.500001),
            ],
            id="just-outside-tolerance",
        ),
        pytest.param(
            [
                _meta("l-tie", polarization=POL_LCP, seconds=1.0),
                _meta("r-first", polarization=POL_RCP, seconds=0.5),
                _meta("r-second", polarization=POL_RCP, seconds=1.5),
            ],
            id="equal-distance-original-order",
        ),
        pytest.param(
            [
                _meta("l-first", polarization=POL_LCP, seconds=1.0),
                _meta("l-second", polarization=POL_LCP, seconds=1.1),
                _meta("r-duplicate-first", polarization=POL_RCP, seconds=1.05),
                _meta("r-duplicate-second", polarization=POL_RCP, seconds=1.05),
            ],
            id="duplicate-times",
        ),
        pytest.param(
            [
                _meta("l149", polarization=POL_LCP, seconds=0.0, freq_mhz=149.0),
                _meta("l238", polarization=POL_LCP, seconds=0.1, freq_mhz=238.0),
                _meta("r238", polarization=POL_RCP, seconds=0.0, freq_mhz=238.0),
                _meta("r149", polarization=POL_RCP, seconds=0.1, freq_mhz=149.0),
            ],
            id="frequency-groups",
        ),
        pytest.param(
            [
                _meta("l-missing", polarization=POL_LCP, seconds=None),
                _meta("r-missing", polarization=POL_RCP, seconds=None),
                _meta("l-valid", polarization=POL_LCP, seconds=2.0),
                _meta("r-valid", polarization=POL_RCP, seconds=2.1),
            ],
            id="missing-times",
        ),
    ],
)
def test_roi_extraction_planner_matches_bruteforce_pairing_oracle(metas):
    tolerance = 0.5
    expected_pairs, expected_skipped = _bruteforce_pairing_oracle(metas, tolerance)

    plan = roi_core._plan_roi_extraction(
        metas,
        mode=POL_SUM,
        tolerance_sec=tolerance,
    )

    assert _paired_paths(plan) == [
        (str(left.path), str(right.path)) for left, right in expected_pairs
    ]
    assert _skipped_identity(plan) == [
        (str(meta.path), flag, paired_path)
        for meta, flag, paired_path in expected_skipped
    ]


def test_roi_extraction_planner_does_not_consume_mismatched_right():
    metas = [
        _meta(
            "l-bad-shape",
            polarization=POL_LCP,
            seconds=0.0,
            shape=(7, 9),
        ),
        _meta("l-good", polarization=POL_LCP, seconds=0.1),
        _meta("r-reusable", polarization=POL_RCP, seconds=0.05),
    ]

    plan = roi_core._plan_roi_extraction(
        metas,
        mode=POL_SUM,
        tolerance_sec=0.5,
    )

    assert _paired_paths(plan) == [
        (str(metas[1].path), str(metas[2].path)),
    ]
    assert _skipped_identity(plan) == [
        (str(metas[0].path), "mismatched_pair", str(metas[2].path)),
    ]


def test_roi_extraction_planner_preserves_single_polarization_and_all_modes():
    metas = [
        _meta("l", polarization=POL_LCP, seconds=0.0),
        _meta("r", polarization=POL_RCP, seconds=0.1),
    ]

    left_only = roi_core._plan_roi_extraction(
        metas,
        mode=POL_LCP,
        tolerance_sec=0.5,
    )
    right_only = roi_core._plan_roi_extraction(
        metas,
        mode=POL_RCP,
        tolerance_sec=0.5,
    )
    all_modes = roi_core._plan_roi_extraction(
        metas,
        mode="all",
        tolerance_sec=0.5,
    )

    assert left_only.selected == (metas[0],)
    assert right_only.selected == (metas[1],)
    assert not left_only.paired and not left_only.skipped
    assert not right_only.paired and not right_only.skipped
    assert all_modes.selected == tuple(metas)
    assert _paired_paths(all_modes) == [(str(metas[0].path), str(metas[1].path))]


def test_roi_extraction_planner_is_subquadratic_and_never_reads_fits(monkeypatch):
    count = 768
    metas = []
    for index in range(count):
        metas.append(
            _meta(
                f"l-{index:04d}",
                polarization=POL_LCP,
                seconds=float(index),
            )
        )
        metas.append(
            _meta(
                f"r-{index:04d}",
                polarization=POL_RCP,
                seconds=float(index) + 0.1,
            )
        )
    same_frequency = roi_core._same_frequency
    frequency_calls = 0
    incompatibility = roi_core._metadata_pair_incompatibility
    incompatibility_calls = 0

    def counted_same_frequency(left, right):
        nonlocal frequency_calls
        frequency_calls += 1
        return same_frequency(left, right)

    def counted_incompatibility(left, right):
        nonlocal incompatibility_calls
        incompatibility_calls += 1
        return incompatibility(left, right)

    monkeypatch.setattr(roi_core, "_same_frequency", counted_same_frequency)
    monkeypatch.setattr(
        roi_core,
        "_metadata_pair_incompatibility",
        counted_incompatibility,
    )
    monkeypatch.setattr(
        roi_core.fits,
        "open",
        lambda *_args, **_kwargs: pytest.fail("planner must not open FITS"),
    )

    plan = roi_core._plan_roi_extraction(
        metas,
        mode=POL_SUM,
        tolerance_sec=0.5,
    )

    assert len(plan.paired) == count
    assert not plan.skipped
    assert frequency_calls <= 20 * len(metas)
    assert incompatibility_calls == count


def _full_grid_oracle(
    data: np.ndarray,
    header: fits.Header,
    roi: roi_core.RadioRoi,
) -> dict[str, float | int | str]:
    arr = np.asarray(data, dtype=float)
    x_arcsec, y_arcsec = roi_core._pixel_center_grid_hpc_arcsec(header, arr.shape)
    if roi.kind == "box":
        bounds = roi.bounds_arcsec
        mask = (
            (x_arcsec >= bounds["left"])
            & (x_arcsec <= bounds["right"])
            & (y_arcsec >= bounds["bottom"])
            & (y_arcsec <= bounds["top"])
        )
    else:
        points = np.column_stack((x_arcsec.ravel(), y_arcsec.ravel()))
        mask = MplPath(np.asarray(roi.vertices_arcsec, dtype=float)).contains_points(
            points,
            radius=1e-12,
        ).reshape(arr.shape)
    roi_count = int(mask.sum())
    finite = mask & np.isfinite(arr)
    valid_count = int(finite.sum())
    if roi_count == 0:
        return {"quality_flag": "empty_roi", "roi_pixel_count": 0}
    if valid_count == 0:
        return {
            "quality_flag": "empty_roi",
            "roi_pixel_count": roi_count,
            "valid_pixel_count": 0,
            "coverage_fraction": 0.0,
            "raw_sum": np.nan,
            "raw_mean": np.nan,
            "raw_peak": np.nan,
        }
    values = arr[finite]
    return {
        "quality_flag": "ok",
        "roi_pixel_count": roi_count,
        "valid_pixel_count": valid_count,
        "coverage_fraction": valid_count / roi_count,
        "raw_sum": float(values.sum()),
        "raw_mean": float(values.mean()),
        "raw_peak": float(values.max()),
    }


@pytest.mark.parametrize(
    ("wcs_kind", "roi"),
    [
        ("positive", roi_core.RadioRoi.from_box(1.0, 1.0, 5.0, 5.0)),
        (
            "negative_pc",
            roi_core.RadioRoi.from_polygon(
                [(-3.5, -1.0), (0.5, -4.0), (3.5, 0.0), (-0.5, 3.0)]
            ),
        ),
        ("cd", roi_core.RadioRoi.from_box(-2.0, -2.0, 3.0, 4.0)),
        ("outside", roi_core.RadioRoi.from_box(100.0, 100.0, 110.0, 110.0)),
    ],
)
def test_roi_crop_measurement_matches_full_grid_oracle(wcs_kind, roi):
    shape = (8, 9)
    header = _header(shape=shape)
    if wcs_kind == "negative_pc":
        header["CDELT1"] = -1.25
        header["CDELT2"] = 0.75
        header["PC1_1"] = 0.8
        header["PC1_2"] = -0.6
        header["PC2_1"] = 0.6
        header["PC2_2"] = 0.8
    elif wcs_kind == "cd":
        for key in ("CDELT1", "CDELT2"):
            del header[key]
        header["CD1_1"] = -0.9
        header["CD1_2"] = 0.2
        header["CD2_1"] = -0.15
        header["CD2_2"] = 1.1
    data = np.arange(np.prod(shape), dtype=float).reshape(shape)
    data[2, 3] = np.nan
    data[5, 6] = np.inf

    expected = _full_grid_oracle(data, header, roi)
    actual = roi_core.measure_radio_roi(data, header, roi)

    assert actual["quality_flag"] == expected["quality_flag"]
    assert actual["roi_pixel_count"] == expected["roi_pixel_count"]
    for key in ("valid_pixel_count", "coverage_fraction", "raw_sum", "raw_mean", "raw_peak"):
        if key not in expected:
            continue
        assert actual[key] == pytest.approx(expected[key], nan_ok=True)


@pytest.mark.parametrize(
    ("wcs_kind", "roi"),
    [
        ("positive", roi_core.RadioRoi.from_box(1.0, 1.0, 5.0, 5.0)),
        (
            "negative_pc",
            roi_core.RadioRoi.from_polygon(
                [(-3.5, -1.0), (0.5, -4.0), (3.5, 0.0), (-0.5, 3.0)]
            ),
        ),
        ("cd", roi_core.RadioRoi.from_box(-2.0, -2.0, 3.0, 4.0)),
        ("outside", roi_core.RadioRoi.from_box(100.0, 100.0, 110.0, 110.0)),
    ],
)
def test_fast_extraction_crop_matches_full_grid_oracle(tmp_path, wcs_kind, roi):
    shape = (8, 9)
    header = _header(shape=shape)
    if wcs_kind == "negative_pc":
        header["CDELT1"] = -1.25
        header["CDELT2"] = 0.75
        header["PC1_1"] = 0.8
        header["PC1_2"] = -0.6
        header["PC2_1"] = 0.6
        header["PC2_2"] = 0.8
    elif wcs_kind == "cd":
        for key in ("CDELT1", "CDELT2"):
            del header[key]
        header["CD1_1"] = -0.9
        header["CD1_2"] = 0.2
        header["CD2_1"] = -0.15
        header["CD2_2"] = 1.1
    data = np.arange(np.prod(shape), dtype=float).reshape(shape)
    data[2, 3] = np.nan
    data[5, 6] = np.inf
    path = _write_fits(
        tmp_path
        / "radio"
        / "149MHz"
        / "LL"
        / "l_20250124044845.fits",
        data,
        header,
    )

    expected = _full_grid_oracle(data, header, roi)
    result = roi_core.extract_radio_roi_lightcurve(
        tmp_path / "radio",
        roi,
        files=[path],
        polarization=POL_LCP,
    ).iloc[0]

    assert result["quality_flag"] == expected["quality_flag"]
    assert result["roi_pixel_count"] == expected["roi_pixel_count"]
    for key in (
        "valid_pixel_count",
        "coverage_fraction",
        "raw_sum",
        "raw_mean",
        "raw_peak",
    ):
        if key in expected:
            assert result[key] == pytest.approx(expected[key], nan_ok=True)


def test_roi_crop_cache_materializes_once_per_wcs_shape_and_roi(monkeypatch):
    cache = roi_core._ROI_CROP_CACHE
    cache.cache_clear()
    header = _header(shape=(32, 40))
    roi = roi_core.RadioRoi.from_box(2.0, 3.0, 15.0, 18.0)
    changed_roi = roi_core.RadioRoi.from_box(3.0, 4.0, 16.0, 19.0)
    original_builder = roi_core._build_roi_crop_plan
    build_calls = 0

    def counted_builder(header_arg, shape_arg, roi_arg):
        nonlocal build_calls
        build_calls += 1
        return original_builder(header_arg, shape_arg, roi_arg)

    monkeypatch.setattr(roi_core, "_build_roi_crop_plan", counted_builder)
    try:
        first = roi_core._roi_crop_plan(header, (32, 40), roi)
        second = roi_core._roi_crop_plan(header.copy(), (32, 40), roi)
        third = roi_core._roi_crop_plan(header, (32, 40), changed_roi)
        info = cache.cache_info()

        assert first is second
        assert third is not first
        assert build_calls == 2
        assert info["hits"] == 1
        assert info["misses"] == 2
        assert info["currsize"] == 2
        assert info["currbytes"] <= info["maxbytes"] == 64 * 1024 * 1024
    finally:
        cache.cache_clear()


def test_simple_lcp_rcp_extraction_opens_each_fits_once(tmp_path, monkeypatch):
    root = tmp_path / "radio"
    shape = (8, 9)
    paths = [
        _write_fits(
            root / "149MHz" / "LL" / "l_20250124044845.fits",
            np.ones(shape),
            _header(shape=shape),
        ),
        _write_fits(
            root / "149MHz" / "RR" / "r_20250124044845.fits",
            np.full(shape, 2.0),
            _header(shape=shape),
        ),
    ]
    roi = roi_core.RadioRoi.from_box(1.0, 1.0, 6.0, 6.0)
    original_open = roi_core.fits.open
    opened: Counter[Path] = Counter()

    def counted_open(filename, *args, **kwargs):
        opened[Path(filename).resolve()] += 1
        return original_open(filename, *args, **kwargs)

    monkeypatch.setattr(roi_core.fits, "open", counted_open)

    result = roi_core.extract_radio_roi_lightcurve(
        root,
        roi,
        files=paths,
        polarization=POL_SUM,
    )

    assert result.loc[0, "quality_flag"] == "ok"
    assert result.loc[0, "raw_sum"] == pytest.approx(108.0)
    assert {path.resolve(): opened[path.resolve()] for path in paths} == {
        path.resolve(): 1 for path in paths
    }


def test_analysis_signature_tracks_file_identity_not_display_only_settings(tmp_path):
    path = _write_fits(
        tmp_path / "149MHz" / "LL" / "frame.fits",
        np.ones((8, 9)),
        _header(),
    )
    roi = roi_core.RadioRoi.from_box(1.0, 1.0, 4.0, 4.0)
    settings = {
        "polarization": POL_SUM,
        "pair_time_tolerance_sec": 0.5,
        "metric": "raw_sum",
        "display_config": {"colormap": "Viridis"},
    }

    first = app._analysis_signature([str(path)], roi, settings)
    display_only = app._analysis_signature(
        [str(path)],
        roi,
        {**settings, "metric": "raw_peak", "display_config": {"colormap": "Hot"}},
    )
    changed_tolerance = app._analysis_signature(
        [str(path)], roi, {**settings, "pair_time_tolerance_sec": 0.25}
    )
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    changed_file = app._analysis_signature([str(path)], roi, settings)

    assert len(first) == 64
    assert display_only == first
    assert changed_tolerance != first
    assert changed_file != first


def test_export_signature_tracks_products_metric_reference_and_display(tmp_path):
    reference = _write_fits(
        tmp_path / "149MHz" / "LL" / "reference.fits",
        np.ones((8, 9)),
        _header(),
    )
    identities = app._selected_file_identities([str(reference)])
    base = app._export_signature(
        analysis_result_signature="analysis-v1",
        product_keys=("csv", "json"),
        metric="raw_sum",
        reference_identities=identities,
        display_config={"colormap": "Viridis"},
    )

    assert len(base) == 64
    assert app._export_signature(
        analysis_result_signature="analysis-v1",
        product_keys=("json", "csv"),
        metric="raw_sum",
        reference_identities=identities,
        display_config={"colormap": "Viridis"},
    ) == base
    assert app._export_signature(
        analysis_result_signature="analysis-v1",
        product_keys=("csv",),
        metric="raw_sum",
        reference_identities=identities,
        display_config={"colormap": "Viridis"},
    ) != base
    assert app._export_signature(
        analysis_result_signature="analysis-v1",
        product_keys=("csv", "json"),
        metric="raw_peak",
        reference_identities=identities,
        display_config={"colormap": "Viridis"},
    ) != base
    assert app._export_signature(
        analysis_result_signature="analysis-v1",
        product_keys=("csv", "json"),
        metric="raw_sum",
        reference_identities=identities,
        display_config={"colormap": "Hot"},
    ) != base


def test_fragment_summaries_and_reference_identity_do_not_live_stat(monkeypatch):
    selected = ["C:/radio/a.fits", "C:/radio/b.fits"]
    manifest = pd.DataFrame(
        {
            "path": selected,
            "size_bytes": [1024, 2048],
        }
    )
    st = SimpleNamespace(
        session_state={
            "dataset_signature": "dataset-v1",
            "selection_revision": 4,
            "loaded_manifest": manifest,
            "reference_grid_signature": "reference-v1",
            "reference_metadata": [],
        }
    )
    reference = SimpleNamespace(
        path=Path(selected[0]),
        hdu_index=0,
        image=np.ones((4, 5)),
    )
    monkeypatch.setattr(
        app,
        "_file_identity",
        lambda *_args, **_kwargs: pytest.fail("fragment rerun must not stat files"),
    )

    first = app._selected_input_size_from_manifest(st, selected)
    second = app._selected_input_size_from_manifest(st, selected)
    identities = app._reference_file_identities(st, [reference])

    assert first == second == (3072, 0)
    assert identities[0] == {"reference_grid_signature": "reference-v1"}
    assert identities[1]["path"] == str(reference.path)


def test_cached_export_injects_preview_curve_and_complete_json_outputs(monkeypatch):
    st = SimpleNamespace(
        session_state={
            "analysis_signature": "analysis-v1",
            "reference_metadata": [],
        }
    )
    df = pd.DataFrame({"raw_sum": [1.0]})
    roi = roi_core.RadioRoi.from_box(0.0, 0.0, 1.0, 1.0)
    settings = {
        "radio_dir": "C:/radio",
        "pattern": "*.fits",
        "recursive": True,
        "polarization": POL_SUM,
        "pair_time_tolerance_sec": 0.5,
        "metric": "raw_sum",
    }

    def fake_artifacts(*_args, **kwargs):
        assert set(kwargs["selected_products"]) == {"csv", "json"}
        return {
            "csv": b"csv-bytes",
            "json": b'{"outputs":{"csv":"radio_roi_statistics.csv"}}',
        }

    monkeypatch.setattr(app, "build_radio_roi_artifacts", fake_artifacts)
    monkeypatch.setattr(
        app,
        "_cached_lightcurve_png",
        lambda *_args, **_kwargs: b"preview-png-bytes",
    )

    artifacts = app._build_cached_export_artifacts(
        st,
        df,
        roi,
        selected_paths=["C:/radio/a.fits"],
        references=[],
        settings=settings,
        display_config={"colormap": "Viridis"},
        product_keys=("csv", "json", "lightcurve_png"),
    )

    saved = json.loads(artifacts["json"].decode("utf-8"))
    assert artifacts["lightcurve_png"] == b"preview-png-bytes"
    assert set(saved["outputs"]) == {"csv", "json", "lightcurve_png"}


def test_prepared_artifacts_write_exact_bytes_to_independent_run_dirs(tmp_path):
    artifacts = {
        "csv": b"csv-payload",
        "json": b"json-payload",
    }

    first = app._write_prepared_artifacts(artifacts, tmp_path / "exports")
    second = app._write_prepared_artifacts(artifacts, tmp_path / "exports")

    assert first["output_dir"] != second["output_dir"]
    for products in (first, second):
        assert products["csv"].read_bytes() == artifacts["csv"]
        assert products["json"].read_bytes() == artifacts["json"]
