from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pytest
from astropy.io import fits


def test_aia_overlay_defaults_keep_gaussian_mode():
    overlay = _import_aia_overlay_with_optional_stubs()

    cfg = overlay.Config()

    assert cfg.radio_overlay_mode == "gaussian"
    assert cfg.enable_spectrogram_panel is False
    assert cfg.make_animation is False


def test_aia_overlay_user_config_maps_raw_spectrogram_and_animation_options():
    overlay = _import_aia_overlay_with_optional_stubs()

    cfg = overlay.apply_aia_radio_hmi_user_config(
        overlay.Config(),
        {
            "radio": {"radio_overlay_mode": "raw"},
            "spectrogram": {
                "enabled": True,
                "file_paths": ["first.fits", "second.fits"],
                "time_start": "2025-05-03T07:20:25",
                "time_end": "2025-05-03T07:22:25",
                "f_start": 80.0,
                "f_end": 300.0,
                "polarization": "sum",
                "vmin": 1.9,
                "vmax": 3.6,
                "use_log10": True,
                "cmap": "jet",
            },
            "animation": {
                "make_animation": True,
                "animation_fps": 12,
                "animation_name": "aia_raw_overlay.mp4",
                "animation_quality": "low",
            },
        },
    )

    assert cfg.radio_overlay_mode == "raw"
    assert cfg.enable_spectrogram_panel is True
    assert cfg.spectrogram_file_paths == ["first.fits", "second.fits"]
    assert cfg.spectrogram_time_start == "2025-05-03T07:20:25"
    assert cfg.spectrogram_time_end == "2025-05-03T07:22:25"
    assert cfg.spectrogram_f_start == 80.0
    assert cfg.spectrogram_f_end == 300.0
    assert cfg.spectrogram_polarization == "sum"
    assert cfg.spectrogram_vmin == 1.9
    assert cfg.spectrogram_vmax == 3.6
    assert cfg.spectrogram_use_log10 is True
    assert cfg.spectrogram_cmap == "jet"
    assert cfg.make_animation is True
    assert cfg.animation_fps == 12
    assert cfg.animation_name == "aia_raw_overlay.mp4"
    assert cfg.animation_quality == "low"


def test_aia_overlay_user_config_maps_drift_and_spectrogram_style_options():
    overlay = _import_aia_overlay_with_optional_stubs()

    cfg = overlay.apply_aia_radio_hmi_user_config(
        overlay.Config(),
        {
            "aia": {
                "aia_panel_layout_style": "mosaic",
                "aia_panel_global_axis_labels": True,
            },
            "spectrogram": {
                "enabled": True,
                "panel_height_ratio": 0.72,
                "hspace": 0.04,
                "major_tick_seconds": 2,
                "auto_time_locator": True,
                "max_time_ticks": 34,
                "clip_current_time_line": True,
                "show_out_of_range_time_note": True,
            },
            "drift_rate": {
                "enabled": True,
                "mode": "manual_json",
                "selection_json": "spectrogram_drift_rate_manual_selection.json",
                "draw_lines": True,
                "draw_endpoints": True,
                "draw_label": True,
                "label_format": "{label}: df/dt={drift_rate:.2f} MHz/s",
                "line_width": 2.2,
                "endpoint_marker": "o",
                "endpoint_size": 30,
                "save_drift_diagnostics": True,
                "drift_diagnostics_csv": "radio_spectrogram_drift_rate_diagnostics.csv",
            },
        },
    )

    assert cfg.aia_panel_layout_style == "mosaic"
    assert cfg.aia_panel_global_axis_labels is True
    assert cfg.spectrogram_panel_height_ratio == pytest.approx(0.72)
    assert cfg.spectrogram_hspace == pytest.approx(0.04)
    assert cfg.spectrogram_major_tick_seconds == 2
    assert cfg.spectrogram_max_time_ticks == 34
    assert cfg.spectrogram_clip_current_time_line is True
    assert cfg.spectrogram_show_out_of_range_time_note is True
    assert cfg.enable_drift_rate_overlay is True
    assert cfg.drift_rate_mode == "manual_json"
    assert (
        cfg.drift_rate_selection_json == "spectrogram_drift_rate_manual_selection.json"
    )
    assert cfg.draw_drift_rate_lines is True
    assert cfg.draw_drift_rate_endpoints is True
    assert cfg.draw_drift_rate_label is True
    assert cfg.drift_rate_line_width == pytest.approx(2.2)
    assert cfg.drift_rate_endpoint_marker == "o"
    assert cfg.drift_rate_endpoint_size == pytest.approx(30)
    assert cfg.save_drift_rate_diagnostics is True

    spectrogram_cfg = overlay._spectrogram_config_dict(cfg)
    assert spectrogram_cfg["enable_drift_rate_overlay"] is True
    assert spectrogram_cfg["drift_rate_mode"] == "manual_json"
    assert spectrogram_cfg["drift_rate_selection_json"].endswith(
        "spectrogram_drift_rate_manual_selection.json"
    )
    assert spectrogram_cfg["spectrogram_major_tick_seconds"] == 2
    assert spectrogram_cfg["spectrogram_max_time_ticks"] == 34


def test_raw_overlay_mode_does_not_call_gaussian_reproject(monkeypatch):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.radio_overlay_mode = "raw"
    expected = object()

    def fail_gaussian(*args, **kwargs):
        raise AssertionError("raw mode must not call Gaussian reproject")

    monkeypatch.setattr(overlay, "reproject_radio_via_gaussian_fit", fail_gaussian)
    monkeypatch.setattr(overlay, "reproject_raw_radio_to_aia", lambda *a, **k: expected)

    result = overlay.reproject_radio_for_overlay(
        np.ones((2, 2), dtype=float),
        None,
        None,
        _FakeAiaMap(),
        cfg,
        fits.Header(),
        source_file="raw.fits",
        band_label="149MHz",
        polarization="RR",
        radio_time=datetime(2025, 5, 3, 7, 20, 25),
    )

    assert result is expected


def test_gaussian_overlay_mode_keeps_existing_gaussian_reproject(monkeypatch):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    expected = object()

    def fail_raw(*args, **kwargs):
        raise AssertionError("Gaussian mode must not call raw reproject")

    monkeypatch.setattr(overlay, "reproject_raw_radio_to_aia", fail_raw)
    monkeypatch.setattr(
        overlay, "reproject_radio_via_gaussian_fit", lambda *a, **k: expected
    )

    result = overlay.reproject_radio_for_overlay(
        np.ones((2, 2), dtype=float),
        None,
        None,
        _FakeAiaMap(),
        cfg,
        fits.Header(),
        source_file="gaussian.fits",
        band_label="149MHz",
        polarization="RR",
        radio_time=datetime(2025, 5, 3, 7, 20, 25),
    )

    assert result is expected


def test_raw_reproject_radec_map_preserves_peak_position(monkeypatch):
    overlay = _import_aia_overlay_with_optional_stubs()
    _install_fake_skycoord(monkeypatch, overlay)
    cfg = overlay.Config()
    cfg.raw_reproject_interpolation_method = "linear"
    radio_data = np.array(
        [
            [1.0, 2.0, 20.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ],
        dtype=float,
    )
    x_grid, y_grid = np.meshgrid(np.arange(3), np.arange(3))
    ra_map = x_grid.astype(float) / 3600.0
    dec_map = y_grid.astype(float) / 3600.0

    result = overlay.reproject_raw_radio_to_aia(
        radio_data,
        ra_map,
        dec_map,
        _FakeAiaMap(shape=(5, 5)),
        cfg,
        radio_header=None,
        source_file="radec.fits",
    )

    assert result is not None
    peak_y, peak_x = np.unravel_index(np.nanargmax(result.model), result.model.shape)
    assert (peak_y, peak_x) == (0, 2)
    assert result.peak_arcsec == pytest.approx((2.0, 0.0))


def test_raw_reproject_header_fallback_preserves_peak_position(monkeypatch):
    overlay = _import_aia_overlay_with_optional_stubs()
    _install_fake_skycoord(monkeypatch, overlay)
    cfg = overlay.Config()
    cfg.use_radec_maps = False
    cfg.raw_reproject_interpolation_method = "linear"
    radio_data = np.array(
        [
            [1.0, 2.0, 3.0],
            [4.0, 30.0, 6.0],
            [7.0, 8.0, 9.0],
        ],
        dtype=float,
    )
    header = fits.Header()
    header["CRPIX1"] = 1.0
    header["CRPIX2"] = 1.0
    header["CRVAL1"] = 0.0
    header["CRVAL2"] = 0.0
    header["CDELT1"] = 1.0
    header["CDELT2"] = 1.0

    result = overlay.reproject_raw_radio_to_aia(
        radio_data,
        None,
        None,
        _FakeAiaMap(shape=(5, 5)),
        cfg,
        radio_header=header,
        source_file="header.fits",
    )

    assert result is not None
    peak_y, peak_x = np.unravel_index(np.nanargmax(result.model), result.model.shape)
    assert (peak_y, peak_x) == (1, 1)
    assert result.peak_arcsec == pytest.approx((1.0, 1.0))


def test_spectrogram_panel_accepts_prebuilt_cache():
    from scripts.radio.core.radio_spectrogram import (
        SpectrogramCache,
        overlay_spectrogram_panel,
    )

    current = datetime(2025, 5, 3, 7, 20, 25)
    time_nums = np.asarray(
        [
            mdates.date2num(datetime(2025, 5, 3, 7, 20, 20)),
            mdates.date2num(current),
            mdates.date2num(datetime(2025, 5, 3, 7, 20, 30)),
        ]
    )
    cache = SpectrogramCache(
        data=np.arange(9, dtype=np.float32).reshape(3, 3),
        time_nums=time_nums,
        display_time_nums=(float(time_nums[0]), float(time_nums[-1])),
        time_datetimes=[],
        freq=np.asarray([100.0, 150.0, 200.0], dtype=np.float32),
        title="Synthetic dynamic spectrum",
        cmap="viridis",
        vmin=None,
        vmax=None,
        cbar_label="intensity",
        source_file="synthetic.fits",
    )

    fig, ax = plt.subplots(figsize=(4, 2))
    try:
        im = overlay_spectrogram_panel(
            ax,
            {"enable_spectrogram_panel": True, "spectrogram_draw_colorbar": False},
            current,
            cache=cache,
        )
        assert im is not None
        assert len(ax.lines) == 1
        assert ax.lines[0].get_xdata()[0] == pytest.approx(mdates.date2num(current))
    finally:
        plt.close(fig)


def test_radio_filename_short_millisecond_suffixes_are_integer_ms():
    overlay = _import_aia_overlay_with_optional_stubs()

    examples = [
        (
            "149MHz_202553_071604_367.fits",
            datetime(2025, 5, 3, 7, 16, 4, 367000),
            ("202553", 26164367),
        ),
        (
            "149MHz_202553_071614_0.fits",
            datetime(2025, 5, 3, 7, 16, 14, 0),
            ("202553", 26174000),
        ),
        (
            "149MHz_202553_071618_13.fits",
            datetime(2025, 5, 3, 7, 16, 18, 13000),
            ("202553", 26178013),
        ),
    ]

    for filename, expected_time, expected_key in examples:
        assert overlay.parse_radio_time_from_filename(filename) == expected_time
        assert overlay._parse_time_from_filename(filename) == expected_key


def test_multi_wave_radio_slots_match_all_bands_by_common_time(tmp_path):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.radio_base_dir = str(tmp_path / "radio")
    cfg.selected_bands = [
        "149MHz",
        "164MHz",
        "190MHz",
        "205MHz",
        "223MHz",
        "238MHz",
    ]
    cfg.combine_polarizations = True
    cfg.polarization_mode = "RR+LL"
    cfg.multi_band_time_tolerance_seconds = 0.1

    for offset_ms, band in enumerate(cfg.selected_bands):
        _touch_radio_pair(
            tmp_path / "radio",
            band,
            f"{band}_202553_072025_{100 + offset_ms:03d}.fits",
        )

    slots = overlay.build_radio_time_slots_for_overlay(cfg)

    assert len(slots) == 1
    slot_index, single_slice_bands = slots[0]
    assert slot_index == 0
    assert list(single_slice_bands) == cfg.selected_bands
    ref_time = datetime(2025, 5, 3, 7, 20, 25, 100000)
    for band in cfg.selected_bands:
        file_item, polarization, radio_time = single_slice_bands[band][0]
        assert isinstance(file_item, tuple)
        assert polarization == "RR+LL"
        assert abs((radio_time - ref_time).total_seconds()) <= 0.1


def test_multi_wave_radio_slots_reject_cross_band_time_mismatch(tmp_path):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.radio_base_dir = str(tmp_path / "radio")
    cfg.selected_bands = ["149MHz", "164MHz"]
    cfg.combine_polarizations = True
    cfg.polarization_mode = "RR+LL"
    cfg.multi_band_time_tolerance_seconds = 0.1

    _touch_radio_pair(tmp_path / "radio", "149MHz", "149MHz_202553_072025_100.fits")
    _touch_radio_pair(tmp_path / "radio", "164MHz", "164MHz_202553_072026_100.fits")

    assert overlay.build_radio_time_slots_for_overlay(cfg) == []


def test_multi_wave_matching_uses_radio_slot_then_nearest_aia_and_hmi(tmp_path):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.radio_base_dir = str(tmp_path / "radio")
    cfg.hmi_base_dir = str(tmp_path / "AIA" / "hmi")
    cfg.aia_panel_wavelengths = [94, 131, 171, 193, 211, 304]
    cfg.aia_panel_base_dir_template = str(tmp_path / "AIA" / "{wave}")
    cfg.selected_bands = ["149MHz", "164MHz"]
    cfg.combine_polarizations = True
    cfg.polarization_mode = "RR+LL"
    cfg.multi_band_time_tolerance_seconds = 0.1
    cfg.aia_time_threshold_seconds = 12.0
    cfg.aia_file_start_idx = 0
    cfg.aia_file_end_idx = None
    cfg.hmi_time_threshold = 1

    _touch_radio_pair(tmp_path / "radio", "149MHz", "149MHz_202553_072025_100.fits")
    _touch_radio_pair(tmp_path / "radio", "164MHz", "164MHz_202553_072025_120.fits")
    for wave in cfg.aia_panel_wavelengths:
        _touch(
            tmp_path
            / "AIA"
            / str(wave)
            / f"aia.lev1_euv_12s.2025-05-03T072025Z.{wave}.image_lev1.fits"
        )
    hmi_file = _touch(
        tmp_path / "AIA" / "hmi" / "hmi.M_45s.20250503_072030_TAI.2.magnetogram.fits"
    )

    matched = overlay.build_multi_wave_matched_pairs(cfg)

    assert len(matched) == 1
    aia_files_by_wave, matched_hmi, sub_tasks = matched[0]
    assert set(aia_files_by_wave) == set(cfg.aia_panel_wavelengths)
    assert matched_hmi == str(hmi_file)
    assert len(sub_tasks) == 1
    _slot_index, single_slice_bands = sub_tasks[0]
    assert list(single_slice_bands) == cfg.selected_bands


def test_multi_wave_figure_creates_six_aia_axes_and_shared_spectrogram_axis():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.aia_panel_wavelengths = [94, 131, 171, 193, 211, 304]
    cfg.enable_spectrogram_panel = True

    fig, axes_by_wave, spectrogram_ax = overlay.create_multi_wave_figure(
        cfg, cfg.aia_panel_wavelengths
    )
    try:
        assert list(axes_by_wave) == cfg.aia_panel_wavelengths
        assert len(axes_by_wave) == 6
        assert spectrogram_ax is not None
        assert len(fig.axes) == 7
    finally:
        plt.close(fig)


def test_multi_wave_figure_mosaic_style_uses_adaptive_canvas_and_global_labels():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.aia_panel_wavelengths = [94, 131, 171, 193, 211, 304]
    cfg.enable_spectrogram_panel = True
    cfg.aia_panel_layout_style = "mosaic"
    cfg.aia_panel_global_axis_labels = True
    cfg.spectrogram_panel_height_ratio = 0.72

    fig, axes_by_wave, spectrogram_ax = overlay.create_multi_wave_figure(
        cfg,
        cfg.aia_panel_wavelengths,
        panel_aspect_ratio=0.75,
    )
    try:
        assert list(axes_by_wave) == cfg.aia_panel_wavelengths
        assert spectrogram_ax is not None
        assert len(fig.axes) == 7
        assert fig.get_figheight() > 11.0
        text_values = [text.get_text() for text in fig.texts]
        assert "Helioprojective Longitude (Solar-X)" in text_values
        assert "Helioprojective Latitude (Solar-Y)" in text_values

        first = axes_by_wave[94].get_position()
        second = axes_by_wave[131].get_position()
        assert first.x1 == pytest.approx(second.x0)
        assert spectrogram_ax.get_position().height > 0.16
    finally:
        plt.close(fig)


def test_multi_wave_mosaic_layout_keeps_spectrogram_title_clear_of_aia_ticks():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.aia_panel_wavelengths = [94, 131, 171, 193, 211, 304]
    cfg.enable_spectrogram_panel = True
    cfg.aia_panel_layout_style = "mosaic"
    cfg.aia_panel_show_axis_labels = False
    cfg.aia_panel_show_tick_labels = True
    cfg.aia_panel_spectrogram_gap = 0.8
    cfg.spectrogram_panel_height_ratio = 0.55

    fig, axes_by_wave, spectrogram_ax = overlay.create_multi_wave_figure(
        cfg,
        cfg.aia_panel_wavelengths,
        panel_aspect_ratio=1.0,
    )
    try:
        ncols = cfg.aia_panel_ncols
        bottom_row_axes = [
            axes_by_wave[wave] for wave in cfg.aia_panel_wavelengths[ncols:]
        ]
        gap = (
            min(ax.get_position().y0 for ax in bottom_row_axes)
            - spectrogram_ax.get_position().y1
        )

        assert gap > 0.05
        assert spectrogram_ax.get_position().height > 0.16

        for index, wave in enumerate(cfg.aia_panel_wavelengths):
            row, _col = divmod(index, ncols)
            ax = axes_by_wave[wave]
            ax.set_xlabel("Solar X (arcsec)")
            ax.set_xticks([0, 1])
            overlay._apply_multi_wave_row_axis_labels(ax, row=row, nrows=2, cfg=cfg)

        for ax in axes_by_wave.values():
            assert ax.get_xlabel() == ""
        assert any(
            label.get_visible()
            for label in axes_by_wave[cfg.aia_panel_wavelengths[-1]].get_xticklabels()
        )
    finally:
        plt.close(fig)


def test_multi_wave_row_axis_labels_keep_x_label_only_on_last_row():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.aia_panel_show_axis_labels = True
    cfg.aia_panel_show_tick_labels = True

    fig, axes = plt.subplots(2, 1)
    try:
        for ax in axes:
            ax.set_xlabel("Solar X (arcsec)")
            ax.set_xticks([0, 1])

        overlay._apply_multi_wave_row_axis_labels(axes[0], row=0, nrows=2, cfg=cfg)
        overlay._apply_multi_wave_row_axis_labels(axes[1], row=1, nrows=2, cfg=cfg)

        assert axes[0].get_xlabel() == ""
        assert axes[1].get_xlabel() == "Solar X (arcsec)"
        assert not any(label.get_visible() for label in axes[0].get_xticklabels())
        assert any(label.get_visible() for label in axes[1].get_xticklabels())
    finally:
        plt.close(fig)


def test_multi_wave_mosaic_row_axis_labels_show_outer_ticks_only():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.aia_panel_layout_style = "mosaic"
    cfg.aia_panel_show_axis_labels = False
    cfg.aia_panel_show_tick_labels = True

    fig, axes = plt.subplots(2, 2)
    try:
        for ax in axes.ravel():
            ax.set_xlabel("Solar X (arcsec)")
            ax.set_ylabel("Solar Y (arcsec)")
            ax.set_xticks([0, 1])
            ax.set_yticks([0, 1])

        for row in range(2):
            for col in range(2):
                overlay._apply_multi_wave_row_axis_labels(
                    axes[row, col],
                    row=row,
                    nrows=2,
                    cfg=cfg,
                    col=col,
                )

        assert not any(label.get_visible() for label in axes[0, 0].get_xticklabels())
        assert any(label.get_visible() for label in axes[1, 0].get_xticklabels())
        assert any(label.get_visible() for label in axes[0, 0].get_yticklabels())
        assert not any(label.get_visible() for label in axes[0, 1].get_yticklabels())
        assert all(ax.get_xlabel() == "" for ax in axes.ravel())
        assert all(ax.get_ylabel() == "" for ax in axes.ravel())
    finally:
        plt.close(fig)


def test_multi_wave_gaussian_overlay_uses_configured_reproject_and_marks_center(
    monkeypatch,
):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.selected_bands = ["149MHz"]
    cfg.combine_polarizations = False
    cfg.polarization_mode = "RR"
    cfg.radio_overlay_mode = "gaussian"
    cfg.show_radio_contours = True
    cfg.mark_radio_center = True
    cfg.contour_levels_peak = [0.5]
    cfg.contour_linewidths = [1.0]

    calls = {}
    expected_time = datetime(2025, 1, 24, 4, 48, 30, 93000)

    monkeypatch.setattr(
        overlay,
        "extract_radio_2d_data",
        lambda *args, **kwargs: (
            np.ones((3, 3), dtype=float),
            None,
            None,
            fits.Header(),
            None,
        ),
    )

    def fail_raw_reproject(*args, **kwargs):
        raise AssertionError("Gaussian six-wave overlay must not call raw reproject")

    def fake_reproject(
        radio_data,
        ra_map,
        dec_map,
        aia_cutout,
        cfg_arg,
        radio_header,
        *,
        source_file,
        band_label,
        polarization,
        radio_time,
    ):
        calls["mode"] = cfg_arg.radio_overlay_mode
        calls["source_file"] = source_file
        calls["band_label"] = band_label
        calls["polarization"] = polarization
        calls["radio_time"] = radio_time
        return overlay.GaussianReprojectResult(
            model=np.asarray([[0.0, 1.0], [1.0, 2.0]], dtype=np.float32),
            center_pixel=(1.0, 1.0),
            center_arcsec=(12.0, 34.0),
            sigma_pixel=(1.0, 1.0),
            theta_rad=0.0,
            amplitude=2.0,
            covariance=None,
        )

    monkeypatch.setattr(overlay, "reproject_raw_radio_to_aia", fail_raw_reproject)
    monkeypatch.setattr(overlay, "reproject_radio_for_overlay", fake_reproject)

    fig, ax = plt.subplots(figsize=(3, 3))
    try:
        first_time = overlay._draw_radio_contours_on_axis(
            ax,
            _FakeAiaMap(shape=(2, 2)),
            [0.0, 2.0, 0.0, 2.0],
            {"149MHz": [("radio.fits", "RR", expected_time)]},
            cfg,
            color_cache=[],
        )

        assert first_time == expected_time
        assert calls == {
            "mode": "gaussian",
            "source_file": "radio.fits",
            "band_label": "149MHz",
            "polarization": "RR",
            "radio_time": expected_time,
        }
        assert any(
            collection.__class__.__name__ == "PathCollection"
            for collection in ax.collections
        )
    finally:
        plt.close(fig)


def test_raw_no_radec_header_overlay_draws_direct_contours_without_reproject(
    monkeypatch,
):
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.selected_bands = ["149MHz"]
    cfg.combine_polarizations = False
    cfg.polarization_mode = "RR"
    cfg.radio_overlay_mode = "raw"
    cfg.use_radec_maps = False
    cfg.show_radio_contours = True
    cfg.mark_radio_center = False
    cfg.contour_levels_peak = [0.5]
    cfg.contour_linewidths = [1.0]

    radio_data = np.asarray([[0.0, 2.0], [4.0, 8.0]], dtype=float)
    header = fits.Header()
    header["CRPIX1"] = 1.0
    header["CRPIX2"] = 1.0
    header["CRVAL1"] = -800.0
    header["CRVAL2"] = -200.0
    header["CDELT1"] = 10.0
    header["CDELT2"] = 20.0
    header["CUNIT1"] = "arcsec"
    header["CUNIT2"] = "arcsec"

    monkeypatch.setattr(
        overlay,
        "extract_radio_2d_data",
        lambda *args, **kwargs: (radio_data, None, None, header, None),
    )

    def fail_reproject(*args, **kwargs):
        raise AssertionError("raw header contour should not call slow reproject")

    monkeypatch.setattr(overlay, "reproject_radio_for_overlay", fail_reproject)

    contour_calls = []

    class CapturingAxis:
        def contour(self, *args, **kwargs):
            contour_calls.append((args, kwargs))
            return object()

    expected_time = datetime(2025, 5, 3, 7, 20, 26, 64000)
    first_time = overlay._draw_radio_contours_on_axis(
        CapturingAxis(),
        _FakeAiaMap(shape=(2, 2)),
        [-800.0, 0.0, -200.0, 400.0],
        {"149MHz": [("radio.fits", "RR", expected_time)]},
        cfg,
        color_cache=[],
    )

    assert first_time == expected_time
    assert len(contour_calls) == 1
    args, kwargs = contour_calls[0]
    assert np.asarray(args[0]).tolist() == [-800.0, -790.0]
    assert np.asarray(args[1]).tolist() == [-200.0, -180.0]
    assert np.asarray(args[2]).tolist() == radio_data.tolist()
    assert kwargs["levels"] == [4.0]
    assert kwargs["origin"] == "lower"


def test_multi_wave_panel_title_reflects_gaussian_mode_without_hmi():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
    cfg.radio_overlay_mode = "gaussian"
    cfg.overlay_hmi = False

    title = overlay._multi_wave_panel_title(
        94, cfg, hmi_file=None, radio_time=datetime(2025, 1, 24, 4, 48, 30)
    )

    assert title == "AIA 94 + Gaussian Radio\n04:48:30 UT"
    assert "HMI" not in title


def test_write_video_from_paths_uses_explicit_frame_order(monkeypatch, tmp_path):
    video = importlib.import_module("scripts.tools.image_sequence_to_video")
    observed = {}

    monkeypatch.setattr(
        video,
        "determine_target_size_for_paths",
        lambda paths, requested_size=None: (8, 6, len(paths), len(paths)),
    )

    def fake_iter(paths, stats, size, workers=1, batch_size=8):
        observed["paths"] = list(paths)
        observed["size"] = size
        return iter([(np.zeros((6, 8, 3), dtype=np.uint8), (8, 6))])

    def fake_ffmpeg(frame_iter, output_path, fps, width, height, quality):
        observed["output_path"] = output_path
        observed["fps"] = fps
        observed["width"] = width
        observed["height"] = height
        observed["quality"] = quality
        list(frame_iter)
        return True

    monkeypatch.setattr(video, "make_frame_iter_from_paths", fake_iter)
    monkeypatch.setattr(video, "write_video_ffmpeg_stream", fake_ffmpeg)

    output = tmp_path / "out.mp4"
    ok = video.write_video_from_paths(
        ["frame_002.png", "frame_001.png"],
        str(output),
        fps=12,
        quality="low",
    )

    assert ok is True
    assert observed["paths"] == ["frame_002.png", "frame_001.png"]
    assert observed["output_path"] == str(output)
    assert observed["fps"] == 12
    assert observed["width"] == 8
    assert observed["height"] == 6
    assert observed["quality"] == "low"


class _FakeCoord:
    def __init__(self, tx, ty):
        self.Tx = tx
        self.Ty = ty


class _FakeWCS:
    def __init__(self, origin_x=0.0, origin_y=0.0):
        self.origin_x = origin_x
        self.origin_y = origin_y

    def world_to_pixel(self, coord):
        return (
            coord.Tx.to_value("arcsec") - self.origin_x,
            coord.Ty.to_value("arcsec") - self.origin_y,
        )


class _FakeAiaMap:
    def __init__(self, shape=(4, 4)):
        self.data = np.zeros(shape, dtype=float)
        self.coordinate_frame = object()
        self.wcs = _FakeWCS()


def _install_fake_skycoord(monkeypatch, overlay):
    monkeypatch.setattr(overlay, "SkyCoord", lambda Tx, Ty, frame: _FakeCoord(Tx, Ty))


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _touch_radio_pair(root: Path, band: str, name: str) -> None:
    _touch(root / band / "RR" / name)
    _touch(root / band / "LL" / name)


def _import_aia_overlay_with_optional_stubs():
    _install_aia_overlay_stubs()
    return importlib.import_module("scripts.radio.legacy.sdo_aia_radio_hmi_overlay")


def _install_aia_overlay_stubs() -> None:
    sunpy = types.ModuleType("sunpy")
    sunpy_coordinates = types.ModuleType("sunpy.coordinates")
    sunpy_map = types.ModuleType("sunpy.map")
    sunpy_map.GenericMap = type("GenericMap", (), {})
    sunpy_map.Map = lambda *args, **kwargs: None
    sunpy.coordinates = sunpy_coordinates
    sunpy.map = sunpy_map

    scipy_ndimage = _import_or_stub_module("scipy.ndimage")
    for name in ("binary_dilation", "find_objects", "gaussian_filter", "label"):
        if not hasattr(scipy_ndimage, name):
            setattr(scipy_ndimage, name, lambda *args, **kwargs: None)
    scipy_interpolate = _import_or_stub_module("scipy.interpolate")
    if not hasattr(scipy_interpolate, "RegularGridInterpolator"):
        scipy_interpolate.RegularGridInterpolator = lambda *args, **kwargs: None
    scipy_optimize = _import_or_stub_module("scipy.optimize")
    if not hasattr(scipy_optimize, "curve_fit"):
        scipy_optimize.curve_fit = lambda *args, **kwargs: None

    _install_missing_modules(
        {
            "sunpy": sunpy,
            "sunpy.coordinates": sunpy_coordinates,
            "sunpy.map": sunpy_map,
            "scipy.ndimage": scipy_ndimage,
            "scipy.interpolate": scipy_interpolate,
            "scipy.optimize": scipy_optimize,
        }
    )


def _import_or_stub_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    if _module_available(name):
        return importlib.import_module(name)
    module = types.ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    sys.modules[name] = module
    return module


def _install_missing_modules(modules: dict[str, types.ModuleType]) -> None:
    for name, module in modules.items():
        if module.__spec__ is None:
            module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
        if name not in sys.modules and not _module_available(name):
            sys.modules[name] = module


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False
