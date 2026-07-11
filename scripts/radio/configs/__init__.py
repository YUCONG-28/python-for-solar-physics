"""Compatibility exports for :mod:`solar_toolkit.radio.config`.

Event modules remain in this package so existing names such as
``scripts.radio.configs.radio_20250124_config`` continue to resolve.
"""

from __future__ import annotations

from solar_toolkit.radio.config import *  # noqa: F403
from solar_toolkit.radio.config import __all__ as __all__
