"""Visualization helper namespace.

English: Shared plotting and media-generation boundary for reusable figure,
movie, and interactive visualization helpers.

中文：可复用绘图、视频和交互式可视化辅助逻辑的公共边界。
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "image_web_viewer": "solar_toolkit.visualization.image_web_viewer",
    "radio_source_trajectory": "solar_toolkit.visualization.radio_source_trajectory",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
