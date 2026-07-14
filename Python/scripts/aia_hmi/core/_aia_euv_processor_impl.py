"""Compatibility alias for the private AIA execution engine.

The historical private path now aliases the package's worker implementation;
public configuration, processing, and CLI imports remain available from the
neighboring ``aia_config``, ``aia_processor``, and ``aia_cli`` wrappers.
"""

from __future__ import annotations

from ._compat import reexport_module

_IMPL = reexport_module("solar_toolkit.aia._euv_processor_impl", globals())
