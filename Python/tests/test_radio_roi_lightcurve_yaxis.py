from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib.figure
import numpy as np
import pandas as pd
import pytest
from astropy.io import fits
from matplotlib.collections import PathCollection

import solar_toolkit.radio.roi_lightcurve as roi_core
import solar_toolkit.radio.roi_lightcurve_app as app
from solar_toolkit.radio.roi_lightcurve import RadioRoi


def _header(
    *,
    freq: float = 149.0,
    date_obs: str = "2025-01-24T04:48:45",
) -> fits.Header:
    header = fits.Header()
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
    header["FREQ"] = freq
    header["FREQUNIT"] = "MHz"
    header["DATE-OBS"] = date_obs
    header["BUNIT"] = "K"
    return header


def _write_fits(
    path: Path,
    data: np.ndarray,
    *,
    header: fits.Header | None = None,
    scaled: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if scaled:
        hdu = fits.PrimaryHDU(data=np.asarray(data, dtype=np.int16), header=header)
        hdu.header["BSCALE"] = 2.0
        hdu.header["BZERO"] = 10.0
        hdu.header["BLANK"] = -32768
    else:
        hdu = fits.PrimaryHDU(data=np.asarray(data), header=header)
    hdu.writeto(path)
    return path


def _full_frame_roi() -> RadioRoi:
    return RadioRoi.from_box(-0.5, -0.5, 3.5, 3.5)


def _curve_df(
    values: list[float],
    *,
    frequencies: list[float] | None = None,
    polarizations: list[str] | None = None,
) -> pd.DataFrame:
    count = len(values)
    return pd.DataFrame(
        {
            "obs_time": pd.date_range(
                "2025-01-24T04:48:00", periods=count, freq="s"
            ).astype(str),
            "freq_mhz": frequencies or [149.0] * count,
            "polarization": polarizations or ["L+R"] * count,
            "bunit": ["K"] * count,
            "quality_flag": ["ok"] * count,
            "raw_sum": values,
            "raw_mean": values,
            "raw_peak": values,
            "filepath": [f"C:/radio/frame_{index:04d}.fits" for index in range(count)],
            "paired_filepath": [""] * count,
        }
    )


def test_paired_float_extraction_preserves_signed_negative_statistics(tmp_path):
    root = tmp_path / "radio"
    left = np.array(
        [
            [-10.0, -20.0, 1.0, 2.0],
            [-10.0, -20.0, 1.0, 2.0],
            [-10.0, -20.0, 1.0, 2.0],
            [-10.0, -20.0, 1.0, 2.0],
        ]
    )
    right = np.array(
        [
            [-2.0, -3.0, 4.0, 5.0],
            [-2.0, -3.0, 4.0, 5.0],
            [-2.0, -3.0, 4.0, 5.0],
            [-2.0, -3.0, 4.0, 5.0],
        ]
    )
    paths = [
        _write_fits(
            root / "149MHz" / "LL" / "l_20250124044845.fits",
            left,
            header=_header(),
        ),
        _write_fits(
            root / "149MHz" / "RR" / "r_20250124044845.fits",
            right,
            header=_header(),
        ),
    ]

    result = roi_core.extract_radio_roi_lightcurve(
        root,
        _full_frame_roi(),
        files=paths,
        polarization="L+R",
    )

    row = result.iloc[0]
    expected = left + right
    assert row["quality_flag"] == "ok"
    assert row["raw_sum"] == pytest.approx(float(expected.sum()))
    assert row["raw_sum"] < 0
    assert row["raw_mean"] == pytest.approx(float(expected.mean()))
    assert row["raw_peak"] == pytest.approx(float(expected.max()))


def test_paired_uint16_extraction_does_not_overflow(tmp_path):
    root = tmp_path / "radio"
    data = np.full((4, 4), 60_000, dtype=np.uint16)
    paths = [
        _write_fits(
            root / "149MHz" / "LL" / "l_20250124044845.fits",
            data,
            header=_header(),
        ),
        _write_fits(
            root / "149MHz" / "RR" / "r_20250124044845.fits",
            data,
            header=_header(),
        ),
    ]

    result = roi_core.extract_radio_roi_lightcurve(
        root,
        _full_frame_roi(),
        files=paths,
        polarization="L+R",
    )

    row = result.iloc[0]
    assert row["quality_flag"] == "ok"
    assert row["raw_sum"] == pytest.approx(16 * 120_000.0)
    assert row["raw_mean"] == pytest.approx(120_000.0)
    assert row["raw_peak"] == pytest.approx(120_000.0)


def test_scaled_blank_fits_matches_astropy_physical_values(tmp_path):
    root = tmp_path / "radio"
    left_raw = np.ones((4, 4), dtype=np.int16)
    right_raw = np.full((4, 4), 2, dtype=np.int16)
    left_raw[0, 0] = -32768
    right_raw[0, 0] = -32768
    paths = [
        _write_fits(
            root / "149MHz" / "LL" / "l_20250124044845.fits",
            left_raw,
            header=_header(),
            scaled=True,
        ),
        _write_fits(
            root / "149MHz" / "RR" / "r_20250124044845.fits",
            right_raw,
            header=_header(),
            scaled=True,
        ),
    ]
    expected_pair = fits.getdata(paths[0]) + fits.getdata(paths[1])

    result = roi_core.extract_radio_roi_lightcurve(
        root,
        _full_frame_roi(),
        files=paths,
        polarization="L+R",
    )

    row = result.iloc[0]
    assert row["quality_flag"] == "ok"
    assert row["roi_pixel_count"] == 16
    assert row["valid_pixel_count"] == 15
    assert row["coverage_fraction"] == pytest.approx(15 / 16)
    assert row["raw_sum"] == pytest.approx(float(np.nansum(expected_pair)))
    assert row["raw_mean"] == pytest.approx(float(np.nanmean(expected_pair)))
    assert row["raw_peak"] == pytest.approx(float(np.nanmax(expected_pair)))


@pytest.mark.parametrize(
    ("limits", "message"),
    [
        ((1.0, 1.0), "minimum must be less"),
        ((2.0, 1.0), "minimum must be less"),
        ((np.nan, 1.0), "finite"),
        ((0.0, np.inf), "finite"),
    ],
)
def test_lightcurve_y_limits_reject_invalid_ranges(tmp_path, limits, message):
    with pytest.raises(ValueError, match=message):
        roi_core.build_radio_roi_artifacts(
            _curve_df([1.0, 2.0]),
            _full_frame_roi(),
            metric="raw_sum",
            lightcurve_y_limits=limits,
            selected_products=("lightcurve_png",),
        )


def test_y_limits_clip_only_png_and_preserve_complete_signed_csv():
    df = _curve_df([-1.0e15, -4.0, 2.0, 8.0])

    artifacts = roi_core.build_radio_roi_artifacts(
        df,
        _full_frame_roi(),
        metric="raw_sum",
        lightcurve_y_limits=(-10.0, 10.0),
        selected_products=("csv", "lightcurve_png"),
    )
    exported = pd.read_csv(pd.io.common.BytesIO(artifacts["csv"]))

    assert artifacts["lightcurve_png"].startswith(b"\x89PNG")
    assert exported["raw_sum"].tolist() == df["raw_sum"].tolist()


def test_plot_applies_y_limits_and_annotates_clipped_samples(tmp_path, monkeypatch):
    captured: dict[str, matplotlib.figure.Figure] = {}

    def capture_figure(figure, *_args, **_kwargs):
        captured["figure"] = figure

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", capture_figure)
    roi_core._plot_radio_roi_lightcurve(
        _curve_df([-1.0e15, -4.0, 2.0, 8.0]),
        tmp_path / "curve.png",
        metric="raw_sum",
        y_limits=(-10.0, 10.0),
    )

    axis = captured["figure"].axes[0]
    assert axis.get_ylim() == pytest.approx((-10.0, 10.0))
    assert any(
        "1 valid samples outside displayed Y range" in item.get_text()
        for item in axis.texts
    )


def test_overview_is_scatter_only_with_unique_frequency_colors_and_markers(
    tmp_path, monkeypatch
):
    captured: dict[str, matplotlib.figure.Figure] = {}

    def capture_figure(figure, *_args, **_kwargs):
        captured["figure"] = figure

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", capture_figure)
    frequencies = [149.0 + 15.0 * index for index in range(16)]
    df = _curve_df(
        [float(index) for index in range(16)],
        frequencies=frequencies,
    )
    extra_polarizations = _curve_df(
        [1.0, 2.0, 3.0],
        frequencies=[149.0, 149.0, 149.0],
        polarizations=["L+R", "LCP", "RCP"],
    )
    df = pd.concat([df, extra_polarizations], ignore_index=True)

    roi_core._plot_radio_roi_lightcurve(
        df,
        tmp_path / "curve.png",
        metric="raw_sum",
    )

    figure = captured["figure"]
    assert len(figure.axes) == 16
    assert all(not axis.lines for axis in figure.axes)
    assert all(
        all(isinstance(artist, PathCollection) for artist in axis.collections)
        for axis in figure.axes
    )
    frequency_colors = {
        axis.get_title(): tuple(axis.collections[0].get_facecolors()[0])
        for axis in figure.axes
    }
    assert len(frequency_colors) == 16
    assert len(set(frequency_colors.values())) == 16

    first_axis = next(
        axis for axis in figure.axes if axis.get_title() == "149 MHz"
    )
    marker_vertices = {
        artist.get_label(): len(artist.get_paths()[0].vertices)
        for artist in first_axis.collections
    }
    assert set(marker_vertices) == {"L+R", "LCP", "RCP"}
    assert len(set(marker_vertices.values())) == 3


def test_overview_uses_independent_frequency_y_ranges(tmp_path, monkeypatch):
    captured: dict[str, matplotlib.figure.Figure] = {}
    monkeypatch.setattr(
        matplotlib.figure.Figure,
        "savefig",
        lambda figure, *_args, **_kwargs: captured.setdefault("figure", figure),
    )
    df = _curve_df(
        [0.0, 1.0, 10.0, 20.0],
        frequencies=[149.0, 149.0, 164.0, 164.0],
    )

    roi_core._plot_radio_roi_lightcurve(
        df,
        tmp_path / "curve.png",
        metric="raw_sum",
        y_limits=(-100.0, 100.0),
        frequency_y_limits={149.0: (-2.0, 2.0), 164.0: None},
    )

    axes = {axis.get_title(): axis for axis in captured["figure"].axes}
    assert axes["149 MHz"].get_ylim() == pytest.approx((-2.0, 2.0))
    assert axes["164 MHz"].get_ylim() != pytest.approx((-100.0, 100.0))
    assert axes["164 MHz"].get_ylim()[0] < 10.0
    assert axes["164 MHz"].get_ylim()[1] > 20.0


def test_marker_size_area_applies_to_all_scatter_views(tmp_path, monkeypatch):
    captured: list[matplotlib.figure.Figure] = []
    monkeypatch.setattr(
        matplotlib.figure.Figure,
        "savefig",
        lambda figure, *_args, **_kwargs: captured.append(figure),
    )
    df = _curve_df(
        [-10.0, 0.0, 10.0, 20.0],
        frequencies=[149.0, 149.0, 164.0, 164.0],
    )
    kwargs = {
        "metric": "raw_sum",
        "frequency_y_limits": {149.0: (-5.0, 5.0), 164.0: (5.0, 15.0)},
        "marker_size": 4.5,
    }

    roi_core._plot_radio_roi_lightcurve(df, tmp_path / "overview.png", **kwargs)
    roi_core._plot_radio_roi_lightcurve_detail(
        df,
        tmp_path / "detail.png",
        detail_frequency_mhz=164.0,
        **kwargs,
    )
    roi_core._plot_radio_roi_lightcurve_normalized(
        df,
        tmp_path / "normalized.png",
        **kwargs,
    )

    for figure in captured:
        collections = [
            collection
            for axis in figure.axes
            for collection in axis.collections
            if isinstance(collection, PathCollection)
        ]
        assert collections
        assert all(
            np.all(collection.get_sizes() == pytest.approx(4.5**2))
            for collection in collections
        )
    assert captured[1].axes[0].get_title().endswith("164 MHz")
    normalized = captured[2].axes[0]
    assert normalized.get_ylim() == pytest.approx((0.0, 1.0))
    assert any(collection.get_facecolors().size == 0 for collection in normalized.collections)


def test_new_lightcurve_products_are_opt_in_and_render_png_bytes():
    df = _curve_df(
        [1.0, 2.0, 3.0, 4.0],
        frequencies=[149.0, 149.0, 164.0, 164.0],
    )

    assert roi_core._normalize_selected_products(None) == (
        "csv",
        "json",
        "reference_png",
        "lightcurve_png",
    )
    artifacts = roi_core.build_radio_roi_artifacts(
        df,
        _full_frame_roi(),
        metric="raw_sum",
        lightcurve_frequency_y_limits={149.0: (0.0, 3.0), 164.0: None},
        lightcurve_marker_size=5.0,
        lightcurve_detail_frequency_mhz=164.0,
        selected_products=(
            "lightcurve_png",
            "lightcurve_detail_png",
            "lightcurve_normalized_png",
            "json",
        ),
    )

    assert {
        "lightcurve_png",
        "lightcurve_detail_png",
        "lightcurve_normalized_png",
    } <= artifacts.keys()
    assert all(
        artifacts[key].startswith(b"\x89PNG")
        for key in (
            "lightcurve_png",
            "lightcurve_detail_png",
            "lightcurve_normalized_png",
        )
    )
    settings = json.loads(artifacts["json"])["settings"]["lightcurve_plot"]
    assert settings["style"] == "scatter"
    assert settings["marker_size_points"] == 5.0
    assert settings["detail_frequency_mhz"] == 164.0
    assert settings["frequency_y_limits"] == {
        "149": [0.0, 3.0],
        "164": None,
    }


def test_y_axis_resolver_supports_robust_full_and_manual_modes():
    values = np.concatenate(([-1.0e15], np.linspace(-10.0, 10.0, 1000)))

    robust = app._resolve_lightcurve_y_limits(values, "Robust auto")
    full = app._resolve_lightcurve_y_limits(values, "Full data")
    manual = app._resolve_lightcurve_y_limits(
        values,
        "Manual",
        manual_limits=(-5.0, 6.0),
    )
    invalid = app._resolve_lightcurve_y_limits(
        values,
        "Manual",
        manual_limits=(1.0, 1.0),
        previous_limits=(-4.0, 4.0),
    )

    assert robust["valid"] is True
    assert robust["limits"] == robust["display_limits"]
    assert robust["limits"][0] > -100.0
    assert full["valid"] is True
    assert full["limits"] is None
    assert full["display_limits"][0] == pytest.approx(-1.0e15)
    assert manual["limits"] == (-5.0, 6.0)
    assert manual["valid"] is True
    assert invalid["valid"] is False
    assert invalid["used_fallback"] is True
    assert invalid["limits"] == (-4.0, 4.0)


def test_robust_y_axis_falls_back_for_small_and_constant_samples():
    small = app._resolve_lightcurve_y_limits(
        np.array([1.0, 2.0, 3.0]),
        "Robust auto",
    )
    constant = app._resolve_lightcurve_y_limits(
        np.full(1000, 100.0),
        "Robust auto",
    )

    assert small["limits"] == (1.0, 3.0)
    assert small["used_fallback"] is True
    assert constant["limits"] == (95.0, 105.0)
    assert constant["used_fallback"] is True


def test_robust_y_axis_uses_documented_point_one_percentiles_by_default():
    values = np.linspace(-40.0, 60.0, 1001)
    lower, upper = np.quantile(values, [0.001, 0.999])
    padding = 0.05 * float(upper - lower)

    resolved = app._resolve_lightcurve_y_limits(values, "Robust auto")

    assert resolved["limits"] == pytest.approx(
        (float(lower - padding), float(upper + padding))
    )


def test_robust_y_axis_tail_guard_handles_three_extremes_in_586_samples():
    values = np.concatenate(
        (
            [-1.564241e15, -7.7e14, -3.2e14],
            np.linspace(-10.0, 10.0, 583),
        )
    )
    guarded_lower, guarded_upper = np.quantile(values, [0.01, 0.99])
    padding = 0.05 * float(guarded_upper - guarded_lower)

    resolved = app._resolve_lightcurve_y_limits(values, "Robust auto")

    assert resolved["limits"] == pytest.approx(
        (
            float(guarded_lower - padding),
            float(guarded_upper + padding),
        )
    )
    assert resolved["limits"][0] > -100.0


def test_curve_diagnostics_counts_and_ranks_complete_outside_rows():
    values = [float(value) for value in range(-100, -75)] + [0.0] * 100
    df = _curve_df(values)

    diagnostics = app._lightcurve_diagnostics(
        df,
        "raw_sum",
        (-10.0, 10.0),
    )

    assert diagnostics["valid_count"] == 125
    assert diagnostics["negative_count"] == 25
    assert diagnostics["outside_count"] == 25
    assert len(diagnostics["outside_rows"]) == 20
    assert diagnostics["outside_rows"].iloc[0]["raw_sum"] == -100.0
    assert {
        "obs_time",
        "freq_mhz",
        "polarization",
        "raw_sum",
        "filepath",
        "paired_filepath",
    }.issubset(diagnostics["outside_rows"].columns)


def test_curve_diagnostics_ignore_invalid_rows_and_detect_extreme_span():
    df = _curve_df([-1.0e15, *np.linspace(-10.0, 10.0, 1000).tolist()])
    df.loc[len(df) - 1, "quality_flag"] = "empty_roi"
    df.loc[len(df) - 2, "raw_sum"] = np.inf

    diagnostics = app._lightcurve_diagnostics(
        df,
        "raw_sum",
        (-20.0, 20.0),
    )

    assert diagnostics["valid_count"] == 999
    assert diagnostics["negative_count"] == 501
    assert diagnostics["outside_count"] == 1
    assert diagnostics["span_ratio"] > 100.0
    assert diagnostics["outside_rows"].iloc[0]["raw_sum"] == -1.0e15


def test_lightcurve_cache_tracks_result_signature_mode_and_limits_without_fits(
    monkeypatch,
):
    st = SimpleNamespace(session_state={})
    df = _curve_df([1.0, 2.0, 3.0])
    calls: list[tuple[str, tuple[float, float] | None]] = []

    def fake_artifacts(*_args, **kwargs):
        calls.append((kwargs["metric"], kwargs["lightcurve_y_limits"]))
        return {"lightcurve_png": f"png-{len(calls)}".encode()}

    monkeypatch.setattr(app, "build_radio_roi_artifacts", fake_artifacts)
    monkeypatch.setattr(
        app,
        "extract_radio_roi_lightcurve",
        lambda *_args, **_kwargs: pytest.fail("Y-axis changes must not read FITS"),
    )

    def cached(result_signature, mode, limits):
        return app._cached_lightcurve_png(
            st,
            df,
            _full_frame_roi(),
            analysis_result_signature=result_signature,
            metric="raw_sum",
            y_axis_mode=mode,
            lightcurve_y_limits=limits,
        )

    first = cached("result-a", "Robust auto", (-5.0, 5.0))
    assert cached("result-a", "Robust auto", (-5.0, 5.0)) == first
    mode_changed = cached("result-a", "Manual", (-5.0, 5.0))
    limits_changed = cached("result-a", "Manual", (-4.0, 4.0))
    result_changed = cached("result-b", "Manual", (-4.0, 4.0))

    assert [first, mode_changed, limits_changed, result_changed] == [
        b"png-1",
        b"png-2",
        b"png-3",
        b"png-4",
    ]
    assert len(calls) == 4


def test_export_signature_tracks_y_axis_mode_and_limits():
    kwargs = {
        "analysis_result_signature": "result-a",
        "product_keys": ("csv", "json", "lightcurve_png"),
        "metric": "raw_sum",
        "reference_identities": [],
        "display_config": {"colormap": "Hot"},
    }
    base = app._export_signature(
        **kwargs,
        y_axis_mode="Robust auto",
        lightcurve_y_limits=(-5.0, 5.0),
    )

    assert app._export_signature(
        **kwargs,
        y_axis_mode="Manual",
        lightcurve_y_limits=(-5.0, 5.0),
    ) != base
    assert app._export_signature(
        **kwargs,
        y_axis_mode="Robust auto",
        lightcurve_y_limits=(-4.0, 4.0),
    ) != base
    assert app._export_signature(
        **{**kwargs, "analysis_result_signature": "result-b"},
        y_axis_mode="Robust auto",
        lightcurve_y_limits=(-5.0, 5.0),
    ) != base


def test_cached_export_records_y_axis_settings_and_reuses_curve_bytes(monkeypatch):
    st = SimpleNamespace(
        session_state={
            "analysis_result_signature": "result-a",
            "reference_metadata": [],
        }
    )
    df = _curve_df([-1.0e15, 1.0, 2.0])
    settings = {
        "radio_dir": "C:/radio",
        "pattern": "*.fits",
        "recursive": True,
        "polarization": "L+R",
        "pair_time_tolerance_sec": 0.5,
        "metric": "raw_sum",
    }
    curve_calls: list[dict] = []

    def fake_curve(*_args, **kwargs):
        curve_calls.append(kwargs)
        return b"same-preview-bytes"

    monkeypatch.setattr(app, "_cached_lightcurve_png", fake_curve)

    artifacts = app._build_cached_export_artifacts(
        st,
        df,
        _full_frame_roi(),
        selected_paths=["C:/radio/a.fits"],
        references=[],
        settings=settings,
        display_config={"colormap": "Hot"},
        product_keys=("json", "lightcurve_png"),
        lightcurve_y_axis={
            "mode": "Manual",
            "limits": (-10.0, 10.0),
            "display_limits": (-10.0, 10.0),
            "valid": True,
        },
    )

    saved = json.loads(artifacts["json"].decode("utf-8"))
    assert artifacts["lightcurve_png"] == b"same-preview-bytes"
    assert saved["settings"]["lightcurve_y_axis"] == {
        "mode": "Manual",
        "limits": [-10.0, 10.0],
    }
    assert curve_calls == [
        {
            "analysis_result_signature": "result-a",
            "metric": "raw_sum",
            "y_axis_mode": "Manual",
            "lightcurve_y_limits": (-10.0, 10.0),
        }
    ]


def test_multiview_cache_tracks_per_frequency_limits_marker_and_detail(monkeypatch):
    st = SimpleNamespace(session_state={})
    df = _curve_df(
        [1.0, 2.0, 3.0, 4.0],
        frequencies=[149.0, 149.0, 164.0, 164.0],
    )
    calls: list[dict] = []

    def fake_artifacts(*_args, **kwargs):
        calls.append(kwargs)
        key = kwargs["selected_products"][0]
        return {key: f"{key}-{len(calls)}".encode()}

    monkeypatch.setattr(app, "build_radio_roi_artifacts", fake_artifacts)
    monkeypatch.setattr(
        app,
        "extract_radio_roi_lightcurve",
        lambda *_args, **_kwargs: pytest.fail(
            "Display-only changes must not read FITS"
        ),
    )
    base_kwargs = {
        "analysis_result_signature": "result-a",
        "metric": "raw_sum",
        "y_axis_mode": "Per frequency",
        "lightcurve_y_limits": None,
        "lightcurve_frequency_y_limits": {
            149.0: (-5.0, 5.0),
            164.0: None,
        },
        "lightcurve_frequency_config": [
            {
                "freq_mhz": 149.0,
                "mode": "Manual",
                "limits": [-5.0, 5.0],
            },
            {"freq_mhz": 164.0, "mode": "Full data", "limits": None},
        ],
        "lightcurve_marker_size": 4.0,
        "lightcurve_detail_frequency_mhz": 149.0,
    }

    overview = app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_png",
        **base_kwargs,
    )
    assert app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_png",
        **{**base_kwargs, "lightcurve_detail_frequency_mhz": 164.0},
    ) == overview
    detail_149 = app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_detail_png",
        **base_kwargs,
    )
    assert app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_detail_png",
        **{
            **base_kwargs,
            "lightcurve_frequency_y_limits": {
                149.0: (-5.0, 5.0),
                164.0: (0.0, 100.0),
            },
            "lightcurve_frequency_config": [
                {
                    "freq_mhz": 149.0,
                    "mode": "Manual",
                    "limits": [-5.0, 5.0],
                },
                {
                    "freq_mhz": 164.0,
                    "mode": "Manual",
                    "limits": [0.0, 100.0],
                },
            ],
        },
    ) == detail_149
    detail_164 = app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_detail_png",
        **{**base_kwargs, "lightcurve_detail_frequency_mhz": 164.0},
    )
    marker_changed = app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_normalized_png",
        **{**base_kwargs, "lightcurve_marker_size": 5.0},
    )
    range_changed = app._cached_lightcurve_png(
        st,
        df,
        _full_frame_roi(),
        product_key="lightcurve_png",
        **{
            **base_kwargs,
            "lightcurve_frequency_y_limits": {
                149.0: (-4.0, 4.0),
                164.0: None,
            },
        },
    )

    assert [overview, detail_149, detail_164, marker_changed, range_changed] == [
        b"lightcurve_png-1",
        b"lightcurve_detail_png-2",
        b"lightcurve_detail_png-3",
        b"lightcurve_normalized_png-4",
        b"lightcurve_png-5",
    ]
    assert len(calls) == 5
    assert calls[0]["lightcurve_marker_size"] == 4.0
    assert calls[1]["lightcurve_detail_frequency_mhz"] == 149.0
    assert calls[2]["lightcurve_detail_frequency_mhz"] == 164.0


def test_export_signature_scopes_detail_frequency_to_detail_product():
    kwargs = {
        "analysis_result_signature": "result-a",
        "metric": "raw_sum",
        "reference_identities": [],
        "display_config": {"colormap": "Hot"},
        "y_axis_mode": "Per frequency",
        "lightcurve_frequency_y_limits": {
            164.0: None,
            149.0: (-5.0, 5.0),
        },
        "lightcurve_frequency_config": [
            {"freq_mhz": 149.0, "mode": "Manual"},
            {"freq_mhz": 164.0, "mode": "Full data"},
        ],
        "lightcurve_marker_size": 3.0,
    }
    overview = app._export_signature(
        **kwargs,
        product_keys=("lightcurve_png",),
        lightcurve_detail_frequency_mhz=149.0,
    )
    assert app._export_signature(
        **kwargs,
        product_keys=("lightcurve_png",),
        lightcurve_detail_frequency_mhz=164.0,
    ) == overview
    assert app._export_signature(
        **{**kwargs, "lightcurve_marker_size": 3.5},
        product_keys=("lightcurve_png",),
        lightcurve_detail_frequency_mhz=149.0,
    ) != overview

    detail = app._export_signature(
        **kwargs,
        product_keys=("lightcurve_detail_png",),
        lightcurve_detail_frequency_mhz=149.0,
    )
    assert app._export_signature(
        **kwargs,
        product_keys=("lightcurve_detail_png",),
        lightcurve_detail_frequency_mhz=164.0,
    ) != detail


def test_cached_export_builds_all_scatter_views_and_records_frequency_config(
    monkeypatch,
):
    st = SimpleNamespace(
        session_state={
            "analysis_result_signature": "result-a",
            "reference_metadata": [],
        }
    )
    df = _curve_df(
        [1.0, 2.0, 3.0, 4.0],
        frequencies=[149.0, 149.0, 164.0, 164.0],
    )
    settings = {
        "radio_dir": "C:/radio",
        "pattern": "*.fits",
        "recursive": True,
        "polarization": "L+R",
        "pair_time_tolerance_sec": 0.5,
        "metric": "raw_sum",
    }
    preview_calls: list[dict] = []

    def fake_curve(*_args, **kwargs):
        preview_calls.append(kwargs)
        return kwargs.get("product_key", "lightcurve_png").encode()

    monkeypatch.setattr(app, "_cached_lightcurve_png", fake_curve)
    y_axis = {
        "mode": "Per frequency",
        "valid": True,
        "marker_size": 4.5,
        "detail_frequency_mhz": 164.0,
        "normalization": "per-frequency displayed Y limits mapped to 0-1",
        "frequencies": [
            {
                "freq_mhz": 149.0,
                "mode": "Manual",
                "limits": (-5.0, 5.0),
                "display_limits": (-5.0, 5.0),
                "valid": True,
                "outside_count": 1,
            },
            {
                "freq_mhz": 164.0,
                "mode": "Full data",
                "limits": None,
                "display_limits": (3.0, 4.0),
                "valid": True,
                "outside_count": 0,
            },
        ],
    }

    artifacts = app._build_cached_export_artifacts(
        st,
        df,
        _full_frame_roi(),
        selected_paths=["C:/radio/a.fits"],
        references=[],
        settings=settings,
        display_config={"colormap": "Hot"},
        product_keys=(
            "json",
            "lightcurve_png",
            "lightcurve_detail_png",
            "lightcurve_normalized_png",
        ),
        lightcurve_y_axis=y_axis,
    )

    assert artifacts["lightcurve_png"] == b"lightcurve_png"
    assert artifacts["lightcurve_detail_png"] == b"lightcurve_detail_png"
    assert artifacts["lightcurve_normalized_png"] == b"lightcurve_normalized_png"
    assert [call["product_key"] for call in preview_calls] == [
        "lightcurve_png",
        "lightcurve_detail_png",
        "lightcurve_normalized_png",
    ]
    assert all(call["lightcurve_marker_size"] == 4.5 for call in preview_calls)
    saved = json.loads(artifacts["json"])
    assert saved["settings"]["lightcurve_plot"]["style"] == "scatter"
    assert saved["settings"]["lightcurve_y_axis"]["frequencies"][0][
        "mode"
    ] == "Manual"
    assert set(saved["outputs"]) == {
        "json",
        "lightcurve_png",
        "lightcurve_detail_png",
        "lightcurve_normalized_png",
    }
