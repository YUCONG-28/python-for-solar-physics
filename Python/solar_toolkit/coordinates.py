"""Deprecated compatibility alias for :mod:`solar_toolkit.map.coordinates`."""

from __future__ import annotations

import sys
from importlib import import_module

from ._deprecation import warn_deprecated

warn_deprecated(
    "solar_toolkit.coordinates",
    since="0.2.0",
    alternative="solar_toolkit.map.coordinates",
    removal="1.0.0",
    stacklevel=2,
)
_target = import_module("solar_toolkit.map.coordinates")
__all__ = _target.__all__
sys.modules[__name__] = _target
