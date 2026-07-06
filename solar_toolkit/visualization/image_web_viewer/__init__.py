"""Local multi-folder image sequence web viewer.

English: Utilities and a Flask app factory for browsing local image sequences,
comparing folders side by side, and exporting videos.

中文：用于浏览本地图片序列、并列比较多个文件夹并导出视频的工具和 Flask
应用工厂。
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "export": "solar_toolkit.visualization.image_web_viewer.export",
    "server": "solar_toolkit.visualization.image_web_viewer.server",
}

__all__ = [
    "create_app",
    "export_composite_video",
    "export_separate_videos",
    "scan_images",
    *_SUBMODULES,
]


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    if name in {"create_app", "scan_images"}:
        module = import_module(_SUBMODULES["server"])
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in {"export_composite_video", "export_separate_videos"}:
        module = import_module(_SUBMODULES["export"])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
