"""X-ray, HXI, Neupert, and DEM workflow helpers.

English: Reusable helpers for loading SXR products, smoothing flux arrays, and
calculating finite-difference derivatives.

中文：用于加载软 X 射线产品、平滑通量数组和计算有限差分导数的可复用工具。
"""

from __future__ import annotations

from importlib import import_module

from .processing import calculate_derivative, smooth_flux_data
from .sxr import load_sxr_data

_SUBMODULES = {
    "aia_dem_inversion": "solar_toolkit.xray_dem.aia_dem_inversion",
    "aia_hxi_overlay": "solar_toolkit.xray_dem.aia_hxi_overlay",
    "cli": "solar_toolkit.xray_dem.cli",
    "dem_radio_source_overlay": "solar_toolkit.xray_dem.dem_radio_source_overlay",
    "hxi": "solar_toolkit.xray_dem.hxi",
    "hxi_image": "solar_toolkit.xray_dem.hxi_image",
    "hxi_lightcurve": "solar_toolkit.xray_dem.hxi_lightcurve",
    "hxi_sxr_comparison": "solar_toolkit.xray_dem.hxi_sxr_comparison",
    "processing": "solar_toolkit.xray_dem.processing",
    "sxr": "solar_toolkit.xray_dem.sxr",
}

_COMPATIBILITY_SUBMODULES = {
    "dem_radio_cli": "solar_toolkit.xray_dem.dem_radio_cli",
}

__all__ = [
    "calculate_derivative",
    "load_sxr_data",
    "smooth_flux_data",
    *_SUBMODULES,
]


def __getattr__(name: str):
    target = _SUBMODULES.get(name) or _COMPATIBILITY_SUBMODULES.get(name)
    if target is not None:
        module = import_module(target)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
