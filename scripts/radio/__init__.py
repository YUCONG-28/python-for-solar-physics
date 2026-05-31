"""Radio analysis entrypoints and modules.

Core modules are lazily re-exported for compatibility with older imports such
as ``from scripts.radio import radio_gaussian_fit`` while keeping import-time
side effects low for command-line entrypoints.
"""

from __future__ import annotations

from importlib import import_module

_CORE_REEXPORTS = {
    "radio_drift_rate": "scripts.radio.core.radio_drift_rate",
    "radio_gaussian_fit": "scripts.radio.core.radio_gaussian_fit",
    "radio_newkirk_extrapolation": "scripts.radio.core.radio_newkirk_extrapolation",
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
