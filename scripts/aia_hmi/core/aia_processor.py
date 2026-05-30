"""Runtime dispatcher for the AIA EUV processor.

The heavy SunPy/Astropy implementation is loaded lazily so importing the
public AIA package remains safe in lightweight test and documentation paths.
"""

from __future__ import annotations

from .aia_config import AIAConfig


def _actual_mode(cfg: AIAConfig) -> str:
    """Normalize compatibility flags into the runtime mode used by the CLI."""
    if cfg.use_test_mode or cfg.mode == "test":
        return "test"
    if cfg.mode == "mosaic" or cfg.multi_band_composite:
        return "mosaic"
    return "single"


def _load_impl():
    """Import the heavy implementation only when processing is requested."""
    from . import _aia_euv_processor_impl

    return _aia_euv_processor_impl


def process_aia_fits(cfg: AIAConfig):
    """Run the legacy-proven AIA processor implementation."""

    return _load_impl().process_aia_fits(cfg)
