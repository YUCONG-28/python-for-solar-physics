"""Radio analysis library APIs.

This package contains reusable radio-analysis helpers. Command-line scripts
remain under ``scripts.radio`` and should call into this package for shared
logic.
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "centers": "solar_toolkit.radio.centers",
    "cli": "solar_toolkit.radio.cli",
    "config": "solar_toolkit.radio.config",
    "coordinates": "solar_toolkit.radio.coordinates",
    "cso": "solar_toolkit.radio.cso",
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
    "pipeline_cli": "solar_toolkit.radio.pipeline_cli",
    "provenance": "solar_toolkit.radio.provenance",
    "quicklook": "solar_toolkit.radio.quicklook",
    "raw_quality": "solar_toolkit.radio.raw_quality",
    "raw_quality_cli": "solar_toolkit.radio.raw_quality_cli",
    "spectrogram": "solar_toolkit.radio.spectrogram",
    "source_map_cli": "solar_toolkit.radio.source_map_cli",
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
