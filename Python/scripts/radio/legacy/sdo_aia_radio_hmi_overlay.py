"""Compatibility alias for :mod:`solar_toolkit.radio.overlay_workflow`."""

from __future__ import annotations

import sys
from importlib import import_module

_TARGET = import_module("solar_toolkit.radio.overlay_workflow")
main = _TARGET.main


if __name__ == "__main__":
    raise SystemExit(main())


sys.modules[__name__] = _TARGET
