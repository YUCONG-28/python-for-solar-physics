"""Compatibility wrapper for :mod:`solar_toolkit.aia.cli`."""

from __future__ import annotations

from ._compat import reexport_module

_IMPL = reexport_module("solar_toolkit.aia.cli", globals())
