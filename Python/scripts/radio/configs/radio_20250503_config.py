"""Compatibility alias for the packaged 2025-05-03 event configuration."""

from __future__ import annotations

import sys

from solar_toolkit.radio.configs import radio_20250503_config as _impl

sys.modules[__name__] = _impl
