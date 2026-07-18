"""Installable event configurations for the maintained Radio workflows."""

from __future__ import annotations

from importlib import import_module

_SUBMODULES = {
    "radio_20250124_center_pm2min_9band_raw_base": (
        "solar_apps.workflows.radio.configs.radio_20250124_center_pm2min_9band_raw_base"
    ),
    "radio_20250124_center_pm2min_9band_raw_ll_full_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_ll_full_config"
    ),
    "radio_20250124_center_pm2min_9band_raw_ll_preview_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_ll_preview_config"
    ),
    "radio_20250124_center_pm2min_9band_raw_rr_full_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_rr_full_config"
    ),
    "radio_20250124_center_pm2min_9band_raw_rr_preview_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_rr_preview_config"
    ),
    "radio_20250124_center_pm2min_9band_raw_rrll_full_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_rrll_full_config"
    ),
    "radio_20250124_center_pm2min_9band_raw_rrll_preview_config": (
        "solar_apps.workflows.radio.configs."
        "radio_20250124_center_pm2min_9band_raw_rrll_preview_config"
    ),
    "radio_20250124_config": "solar_apps.workflows.radio.configs.radio_20250124_config",
    "radio_20250503_config": "solar_apps.workflows.radio.configs.radio_20250503_config",
}

DEFAULT_CONFIG_NAME = "solar_apps.workflows.radio.configs.radio_20250124_config"

__all__ = ["DEFAULT_CONFIG_NAME", *sorted(_SUBMODULES)]


def __getattr__(name: str):
    if name in _SUBMODULES:
        module = import_module(_SUBMODULES[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
