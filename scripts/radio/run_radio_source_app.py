"""Compatibility entry point for :mod:`solar_toolkit.radio.source_app`.

The Streamlit implementation is package-owned; this source-checkout path is
retained for existing launch commands and imports.
"""

from __future__ import annotations

import sys
from importlib import import_module

_MODULE_NAME = "solar_toolkit.radio.source_app"
_target = import_module(_MODULE_NAME)
__all__ = _target.__all__

if __name__ == "__main__":
    raise SystemExit(_target.main())

sys.modules[__name__] = _target
