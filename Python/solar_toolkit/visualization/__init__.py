"""Public visualization helper namespace.

English: Shared plotting, font configuration, media-generation, and
interactive visualization helpers.

中文：共享绘图、字体配置、媒体生成和交互式可视化工具的公共命名空间。
"""

from __future__ import annotations

from importlib import import_module as _import_module

_DEFAULT_CHINESE_FONT_CANDIDATES = [
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "DejaVu Sans",
]

_SUBMODULES = {
    "frames": "solar_toolkit.visualization.frames",
    "image_web_viewer": "solar_toolkit.visualization.image_web_viewer",
    "media": "solar_toolkit.visualization.media",
    "plotting": "solar_toolkit.visualization.plotting",
    "radio_source_trajectory": "solar_toolkit.visualization.radio_source_trajectory",
    "radio_source_video": "solar_toolkit.visualization.radio_source_video",
    "stereo_euvi_overview": "solar_toolkit.visualization.stereo_euvi_overview",
    "stereo_euvi_roi_movie": "solar_toolkit.visualization.stereo_euvi_roi_movie",
    "suvi_quadrant": "solar_toolkit.visualization.suvi_quadrant",
    "video_cli": "solar_toolkit.visualization.video_cli",
}

_COMPATIBILITY_SUBMODULES = {
    "media_assets": "solar_toolkit.visualization._media_assets",
}

__all__ = ["configure_chinese_fonts", *_SUBMODULES]


def configure_chinese_fonts(candidates: list[str] | None = None) -> str | None:
    """Configure matplotlib with the first available CJK-capable font."""

    import matplotlib.font_manager
    from matplotlib import rcParams

    candidates = candidates or _DEFAULT_CHINESE_FONT_CANDIDATES
    available = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    selected = next((font for font in candidates if font in available), None)
    if selected is None:
        return None
    sans = [font for font in rcParams.get("font.sans-serif", []) if font != selected]
    rcParams["font.sans-serif"] = [selected, *sans]
    rcParams["font.family"] = "sans-serif"
    rcParams["axes.unicode_minus"] = False
    return selected


def __getattr__(name: str):
    """Lazily import public modules and compatibility aliases."""

    target = _SUBMODULES.get(name) or _COMPATIBILITY_SUBMODULES.get(name)
    if target is not None:
        module = _import_module(target)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return the stable public visualization namespace."""

    return sorted(__all__)
