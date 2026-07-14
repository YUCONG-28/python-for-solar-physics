"""Compatibility namespace for AIA/HMI workflow helpers."""

from .aia_config import AIAConfig
from .aia_processor import process_aia_fits

__all__ = ["AIAConfig", "process_aia_fits"]
