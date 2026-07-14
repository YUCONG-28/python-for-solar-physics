"""Compatibility alias for :mod:`solar_toolkit.visualization._media_assets`.

This module path is retained during the compatibility window. New internal
code should use the private canonical resource package instead.

.. deprecated:: 0.2.0
   This alias will remain available until at least version 1.0.0 and until
   compatibility validation permits its removal.
"""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_target = _import_module("solar_toolkit.visualization._media_assets")
_sys.modules[__name__] = _target
