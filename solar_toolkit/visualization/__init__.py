"""Visualization helper namespace.

English: Shared plotting, font configuration, media-generation, and
interactive visualization helpers.

中文: 可复用绘图、字体配置、媒体生成和交互式可视化辅助工具命名空间。
"""

from __future__ import annotations

from importlib import import_module

DEFAULT_CHINESE_FONT_CANDIDATES = [
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "DejaVu Sans",
]

_SUBMODULES = {
    "image_web_viewer": "solar_toolkit.visualization.image_web_viewer",
    "radio_source_trajectory": "solar_toolkit.visualization.radio_source_trajectory",
}

__all__ = ["configure_chinese_fonts", *_SUBMODULES]


def configure_chinese_fonts(candidates: list[str] | None = None) -> str | None:
    """Configure matplotlib with the first available CJK-capable font."""

    import matplotlib.font_manager
    from matplotlib import rcParams

    candidates = candidates or DEFAULT_CHINESE_FONT_CANDIDATES
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
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
