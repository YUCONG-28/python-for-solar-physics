from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
import types
from datetime import datetime

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
