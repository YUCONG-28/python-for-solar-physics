"""Local data inventory helpers.

English: Small manifest helpers for recording local observation files without
performing archive queries or downloads.

中文：用于记录本地观测文件的小型清单工具，不执行联网查询或下载。
"""

from __future__ import annotations

from importlib import import_module

from .inventory import ObservationFile, build_inventory

_SUBMODULES = {
    "inventory": "solar_toolkit.data.inventory",
    "stereo_manifest": "solar_toolkit.data.stereo_manifest",
}

__all__ = ["ObservationFile", "build_inventory", *_SUBMODULES]


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
