"""Path-only local overrides for packaged radio event configurations."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from solar_apps.platform.config import load_script_config

_PATH_KEYS = frozenset(
    {
        "aia_base_dir",
        "aia_panel_base_dir_template",
        "data_dir",
        "file_path",
        "file_paths",
        "hmi_base_dir",
        "multi_band_root",
        "output_dir",
        "radio_base_dir",
        "single_file_path",
    }
)


def apply_event_path_overrides(
    event_config: dict[str, Any], script_key: str
) -> dict[str, Any]:
    """Apply local YAML values while rejecting non-path configuration changes."""

    overrides = load_script_config(script_key, {})
    _merge_path_values(event_config, overrides, script_key)
    return event_config


def _merge_path_values(
    target: dict[str, Any], overrides: Mapping[str, Any], section: str
) -> None:
    for key, value in overrides.items():
        location = f"{section}.{key}"
        if key not in target:
            raise KeyError(f"Unknown radio path override: {location}")
        target_value = target[key]
        if isinstance(value, Mapping):
            if not isinstance(target_value, dict):
                raise ValueError(f"Radio path override must be a value: {location}")
            _merge_path_values(target_value, value, location)
            continue
        if key not in _PATH_KEYS:
            raise ValueError(f"Only path fields may be overridden: {location}")
        target[key] = deepcopy(value)
