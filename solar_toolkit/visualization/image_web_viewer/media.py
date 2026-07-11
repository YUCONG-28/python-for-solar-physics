"""Compatibility alias for :mod:`solar_toolkit.visualization.media`."""

from __future__ import annotations

import sys

from solar_toolkit.visualization import media as _shared_media

sys.modules[__name__] = _shared_media
