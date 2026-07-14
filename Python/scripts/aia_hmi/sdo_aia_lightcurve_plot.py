"""Compatibility alias for :mod:`solar_toolkit.aia.lightcurve_plot`."""

from __future__ import annotations

import sys
from importlib import import_module

_target = import_module("solar_toolkit.aia.lightcurve_plot")
__all__ = _target.__all__

if __name__ == "__main__":
    raise SystemExit(_target.main())

sys.modules[__name__] = _target
