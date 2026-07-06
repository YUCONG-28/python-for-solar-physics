"""SDO/HMI helper namespace.

English: Public boundary for HMI-oriented helpers, including magnetogram
plotting, FITS renaming, and AIA/HMI overlay workflows that still run through
thin scripts.

中文：SDO/HMI 公共命名空间，覆盖磁图绘制、FITS 规范命名，以及仍由薄脚本
调用的 AIA/HMI 叠加流程。
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "fits_rename": "solar_toolkit.hmi.fits_rename",
    "magnetogram": "solar_toolkit.hmi.magnetogram",
    "overlay": "solar_toolkit.hmi.overlay",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
