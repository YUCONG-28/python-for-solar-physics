"""SDO/HMI helper namespace.

English: Public boundary for HMI-oriented helpers, including magnetogram
plotting, FITS renaming, and package-owned AIA/HMI overlay workflows. Historical
scripts are thin compatibility entry points.

中文：SDO/HMI 公共命名空间，覆盖磁图绘制、FITS 规范命名和包内 AIA/HMI
叠加流程；历史脚本仅保留薄兼容入口。
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "fits_rename": "solar_toolkit.hmi.fits_rename",
    "magnetogram": "solar_toolkit.hmi.magnetogram",
    "overlay": "solar_toolkit.hmi.overlay",
    "processing": "solar_toolkit.hmi.processing",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
