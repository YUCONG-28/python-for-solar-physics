"""SDO/AIA processing APIs.

English: Public AIA library boundary for configuration, FITS selection,
difference images, mosaics, background loading, and the lazy EUV processor
dispatcher.

中文：SDO/AIA 公共库边界，包含配置、FITS 选择、差分图、拼图、背景读取
以及延迟加载的 EUV 处理调度入口。
"""

from __future__ import annotations

from importlib import import_module

from .config import AIAConfig
from .processor import process_aia_fits

_SUBMODULES = {
    "background": "solar_toolkit.aia.background",
    "cli": "solar_toolkit.aia.cli",
    "config": "solar_toolkit.aia.config",
    "difference": "solar_toolkit.aia.difference",
    "io": "solar_toolkit.aia.io",
    "lightcurve_extraction": "solar_toolkit.aia.lightcurve_extraction",
    "lightcurve_plot": "solar_toolkit.aia.lightcurve_plot",
    "mosaic": "solar_toolkit.aia.mosaic",
    "processor": "solar_toolkit.aia.processor",
}

__all__ = ["AIAConfig", "process_aia_fits", *_SUBMODULES]


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
