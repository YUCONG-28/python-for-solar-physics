from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
import tempfile
import types
from pathlib import Path


def test_aia_overlay_legend_includes_all_selected_bands():
    overlay = _import_aia_overlay_with_optional_stubs()
    cfg = overlay.Config()
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
    cfg.weighted_average = False

    handles = overlay._build_selected_band_legend_elements(cfg, color_cache=[])

    assert [handle.get_label() for handle in handles] == [
        "149MHz (RR+LL sum)",
        "164MHz (RR+LL sum)",
        "190MHz (RR+LL sum)",
        "205MHz (RR+LL sum)",
        "223MHz (RR+LL sum)",
        "238MHz (RR+LL sum)",
    ]


def test_multi_band_output_dir_resolves_inside_analysis_subdir_without_creating_root():
    source_map = _import_source_map_with_optional_stubs()
    cfg = {
        "polarization": "RR+LL",
        "multi_band_output_subdir": "multi_band_{polar}",
        "analysis_subdir": "gaussian_spectrogram_overlay",
    }

    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        resolved = source_map._resolve_multi_band_output_dir(str(output_dir), cfg)

        assert (
            resolved == output_dir / "gaussian_spectrogram_overlay" / "multi_band_RR+LL"
        )
        assert not (output_dir / "multi_band_RR+LL").exists()


def _import_source_map_with_optional_stubs():
    _install_source_map_stubs()
    return importlib.import_module(
        "scripts.radio.legacy.radio_source_map_plot_gaussian_overlay"
    )


def _import_aia_overlay_with_optional_stubs():
    _install_aia_overlay_stubs()
    return importlib.import_module("scripts.radio.legacy.sdo_aia_radio_hmi_overlay")


def _install_source_map_stubs() -> None:
    scipy = types.ModuleType("scipy")
    scipy_ndimage = types.ModuleType("scipy.ndimage")
    scipy_optimize = types.ModuleType("scipy.optimize")
    tqdm_module = types.ModuleType("tqdm")
    for name in ("binary_dilation", "find_objects", "label", "median_filter"):
        setattr(scipy_ndimage, name, lambda *args, **kwargs: None)
    scipy_optimize.curve_fit = lambda *args, **kwargs: None
    tqdm_module.tqdm = lambda iterable=None, *args, **kwargs: iterable
    _install_missing_modules(
        {
            "scipy": scipy,
            "scipy.ndimage": scipy_ndimage,
            "scipy.optimize": scipy_optimize,
            "tqdm": tqdm_module,
        }
    )


def _install_aia_overlay_stubs() -> None:
    _install_source_map_stubs()

    sunpy = types.ModuleType("sunpy")
    sunpy_coordinates = types.ModuleType("sunpy.coordinates")
    sunpy_map = types.ModuleType("sunpy.map")
    sunpy_map.GenericMap = type("GenericMap", (), {})
    sunpy_map.Map = lambda *args, **kwargs: None
    sunpy.coordinates = sunpy_coordinates
    sunpy.map = sunpy_map

    scipy_ndimage = _import_or_stub_module("scipy.ndimage")
    if not hasattr(scipy_ndimage, "gaussian_filter"):
        scipy_ndimage.gaussian_filter = lambda *args, **kwargs: None
    scipy_interpolate = _import_or_stub_module("scipy.interpolate")
    if not hasattr(scipy_interpolate, "RegularGridInterpolator"):
        scipy_interpolate.RegularGridInterpolator = lambda *args, **kwargs: None

    _install_missing_modules(
        {
            "sunpy": sunpy,
            "sunpy.coordinates": sunpy_coordinates,
            "sunpy.map": sunpy_map,
            "scipy.ndimage": scipy_ndimage,
            "scipy.interpolate": scipy_interpolate,
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
