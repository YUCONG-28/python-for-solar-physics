"""Radio analysis entrypoints and modules.

Core modules are lazily re-exported for compatibility with older imports such
as ``from scripts.radio import radio_gaussian_fit`` while keeping import-time
side effects low for command-line entrypoints.
"""

from __future__ import annotations

from importlib import import_module

_CORE_REEXPORTS = {
    "radio_coordinates": "solar_toolkit.radio.coordinates",
    "radio_drift_rate": "scripts.radio.core.radio_drift_rate",
    "radio_frequency_priority_diagnostics": (
        "solar_toolkit.radio.frequency_priority_diagnostics"
    ),
    "radio_gaussian_fit": "solar_toolkit.radio.gaussian",
    "radio_height_comparison": "solar_toolkit.radio.height_comparison",
    "radio_io": "solar_toolkit.radio.io",
    "radio_newkirk_extrapolation": "solar_toolkit.radio.newkirk",
    "radio_quicklook": "solar_toolkit.radio.quicklook",
    "radio_raw_quality": "scripts.radio.core.radio_raw_quality",
    "radio_spectrogram": "scripts.radio.core.radio_spectrogram",
    "run_radio_raw_quality": "scripts.radio.run_radio_raw_quality",
}

__all__ = sorted(_CORE_REEXPORTS)


def __getattr__(name: str):
    if name in _CORE_REEXPORTS:
        module = import_module(_CORE_REEXPORTS[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
