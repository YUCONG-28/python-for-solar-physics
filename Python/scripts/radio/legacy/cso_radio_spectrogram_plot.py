"""Compatibility entry point for :mod:`solar_toolkit.radio.cso_workflow`.

The historical script remains executable, while the maintained workflow now
lives in the installable package.  Imports resolve to the canonical module so
there is no second implementation to maintain.
"""

from __future__ import annotations

import sys
from importlib import import_module

_MODULE_NAME = "solar_toolkit.radio.cso_workflow"
_target = import_module(_MODULE_NAME)
__all__ = _target.__all__

if __name__ == "__main__":
    raise SystemExit(_target.main())

sys.modules[__name__] = _target
