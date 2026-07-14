"""Compatibility alias for the packaged example Radio pipeline config."""

from __future__ import annotations

import sys
from importlib import import_module

_IMPL = import_module("solar_toolkit.radio.configs.example_radio_pipeline_config")
sys.modules[__name__] = _IMPL
