"""Radio analysis library APIs.

This package contains reusable radio-analysis helpers. Command-line scripts
remain under ``scripts.radio`` and should call into this package for shared
logic.
"""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "coordinates": "solar_toolkit.radio.coordinates",
    "frequency_priority_diagnostics": "solar_toolkit.radio.frequency_priority_diagnostics",
    "gaussian": "solar_toolkit.radio.gaussian",
    "height_comparison": "solar_toolkit.radio.height_comparison",
    "height_plots": "solar_toolkit.radio.height_plots",
    "io": "solar_toolkit.radio.io",
    "newkirk": "solar_toolkit.radio.newkirk",
    "output_paths": "solar_toolkit.radio.output_paths",
    "quicklook": "solar_toolkit.radio.quicklook",
}

__all__ = sorted(_SUBMODULES)


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
