"""Configuration loading helpers for radio entrypoints."""

from __future__ import annotations

import copy
import importlib
from types import ModuleType

DEFAULT_CONFIG_NAME = "radio_20250124_config"
DEFAULT_AIA_CONFIG_NAME = "aia_radio_hmi_20250124_config"
DEFAULT_NEWKIRK_CONFIG = {
    "enabled": True,
    "multipliers": [1, 2, 4],
    "harmonics": [1, 2],
    "solar_radius_arcsec": 959.63,
    "los_sign": 1,
}


def _normalize_config_module_name(config_name: str | None) -> str:
    name = (config_name or DEFAULT_CONFIG_NAME).strip()
    if not name:
        name = DEFAULT_CONFIG_NAME
    if name.endswith(".py"):
        name = name[:-3]
    if name.startswith("scripts.radio.configs."):
        return name
    if "." in name:
        return name
    return f"scripts.radio.configs.{name}"


def load_radio_config_module(config_name: str | None = None) -> ModuleType:
    """Load a config module from ``scripts.radio.configs``."""
    return importlib.import_module(_normalize_config_module_name(config_name))


def load_radio_user_config(config_name: str | None = None):
    """
    Load a radio event config.

    Returns ``(USER_CONFIG, NEWKIRK_CONFIG)``. The config name may be either a
    short module name such as ``radio_20250124_config`` or a fully qualified
    module path such as ``scripts.radio.configs.radio_20250124_config``.
    """
    module = load_radio_config_module(config_name)
    user_config = copy.deepcopy(getattr(module, "USER_CONFIG", {}) or {})
    newkirk_config = dict(DEFAULT_NEWKIRK_CONFIG)
    newkirk_config.update(copy.deepcopy(getattr(module, "NEWKIRK_CONFIG", {}) or {}))
    return user_config, newkirk_config


def load_aia_radio_hmi_user_config(config_name: str | None = None):
    """Load AIA/HMI/radio overlay config from a config module."""
    module = load_radio_config_module(config_name)
    config = copy.deepcopy(getattr(module, "AIA_RADIO_HMI_CONFIG", {}) or {})
    if config:
        return config
    if (config_name or DEFAULT_CONFIG_NAME).strip() == DEFAULT_CONFIG_NAME:
        fallback = load_radio_config_module(DEFAULT_AIA_CONFIG_NAME)
        return copy.deepcopy(getattr(fallback, "AIA_RADIO_HMI_CONFIG", {}) or {})
    return {}
