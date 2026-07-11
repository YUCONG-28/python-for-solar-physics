"""Compatibility alias for the packaged 9-band event-config builder."""

from __future__ import annotations

import sys
from importlib import import_module

_IMPL = import_module(
    "solar_toolkit.radio.configs.radio_20250124_center_pm2min_9band_raw_base"
)
sys.modules[__name__] = _IMPL
