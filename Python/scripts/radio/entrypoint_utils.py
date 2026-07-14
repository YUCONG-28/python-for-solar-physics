"""Compatibility wrapper for :mod:`solar_toolkit.radio.entrypoint_utils`."""

from __future__ import annotations

from scripts.radio.core._compat import reexport_module

_IMPL = reexport_module("solar_toolkit.radio.entrypoint_utils", globals())
