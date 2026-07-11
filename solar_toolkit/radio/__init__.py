"""Radio analysis library and workflow APIs.

English: Package-owned configuration, scientific helpers, source-map,
pipeline, overlay, CSO, diagnostics, and local application workflows.
Historical ``scripts.radio`` paths are compatibility entry points only.

中文：包内统一维护射电配置、科学计算、源图、pipeline、overlay、CSO、诊断与本地应用
工作流；历史 ``scripts.radio`` 路径只作为兼容入口。
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "centers": "solar_toolkit.radio.centers",
    "cli": "solar_toolkit.radio.cli",
    "config": "solar_toolkit.radio.config",
    "configs": "solar_toolkit.radio.configs",
    "coordinates": "solar_toolkit.radio.coordinates",
    "cso": "solar_toolkit.radio.cso",
    "cso_workflow": "solar_toolkit.radio.cso_workflow",
    "frequency_priority_diagnostics": "solar_toolkit.radio.frequency_priority_diagnostics",
    "gaussian": "solar_toolkit.radio.gaussian",
    "gaussian_background": "solar_toolkit.radio.gaussian_background",
    "gaussian_diagnostics": "solar_toolkit.radio.gaussian_diagnostics",
    "gaussian_fit": "solar_toolkit.radio.gaussian_fit",
    "gaussian_io": "solar_toolkit.radio.gaussian_io",
    "gaussian_masks": "solar_toolkit.radio.gaussian_masks",
    "gaussian_models": "solar_toolkit.radio.gaussian_models",
    "height_comparison": "solar_toolkit.radio.height_comparison",
    "height_plots": "solar_toolkit.radio.height_plots",
    "io": "solar_toolkit.radio.io",
    "newkirk": "solar_toolkit.radio.newkirk",
    "output_paths": "solar_toolkit.radio.output_paths",
    "overlay_cli": "solar_toolkit.radio.overlay_cli",
    "overlay_workflow": "solar_toolkit.radio.overlay_workflow",
    "pipeline_cli": "solar_toolkit.radio.pipeline_cli",
    "pipeline_workflow": "solar_toolkit.radio.pipeline_workflow",
    "provenance": "solar_toolkit.radio.provenance",
    "quicklook": "solar_toolkit.radio.quicklook",
    "raw_quality": "solar_toolkit.radio.raw_quality",
    "raw_quality_cli": "solar_toolkit.radio.raw_quality_cli",
    "spectrogram": "solar_toolkit.radio.spectrogram",
    "source_map_cli": "solar_toolkit.radio.source_map_cli",
    "source_map_workflow": "solar_toolkit.radio.source_map_workflow",
    "source_app": "solar_toolkit.radio.source_app",
    "source_app_launcher": "solar_toolkit.radio.source_app_launcher",
    "trajectory": "solar_toolkit.radio.trajectory",
    "trajectory_cli": "solar_toolkit.radio.trajectory_cli",
    "drift_rate": "solar_toolkit.radio.drift_rate",
    "drift_products": "solar_toolkit.radio.drift_products",
    "entrypoint_utils": "solar_toolkit.radio.entrypoint_utils",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
