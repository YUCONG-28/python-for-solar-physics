"""Optional local path configuration for standalone solar-physics scripts."""

from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _deep_update(base: dict[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def _config_path() -> Path:
    env_path = os.environ.get("SOLAR_PHYSICS_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return _repo_root() / "configs" / "paths.local.yaml"


def load_script_config(
    script_key: str, defaults: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Load optional YAML overrides for one script.

    The repository ships only ``configs/paths.example.yaml``. Users can copy it
    to ``configs/paths.local.yaml`` or point ``SOLAR_PHYSICS_CONFIG`` at another
    YAML file. Missing files or missing script sections leave defaults unchanged.
    """

    merged: dict[str, Any] = deepcopy(dict(defaults or {}))
    path = _config_path()
    if not path.exists():
        return merged

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    scripts = data.get("scripts", data)
    overrides = scripts.get(script_key, {})
    if not isinstance(overrides, Mapping):
        raise ValueError(f"Config section for {script_key!r} must be a mapping")

    return _deep_update(merged, overrides)


def apply_config_to_object(obj: Any, script_key: str) -> Any:
    """Apply optional config values to attributes already defined on an object."""

    for key, value in load_script_config(script_key, {}).items():
        if hasattr(obj, key):
            setattr(obj, key, value)
    return obj
