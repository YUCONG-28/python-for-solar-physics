"""Compatibility alias for :mod:`solar_toolkit.aia._euv_processor_impl`.

The historical private module contained a full copy of the AIA processor.
Keeping a real module alias preserves old imports while ensuring the reusable
package is the only implementation maintained during the migration window.
"""

from __future__ import annotations

from ._compat import reexport_module

_IMPL = reexport_module("solar_toolkit.aia._euv_processor_impl", globals())
