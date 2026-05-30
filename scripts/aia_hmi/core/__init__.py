"""Core modules for AIA/HMI workflows."""

from .aia_config import AIAConfig
from .aia_processor import process_aia_fits

__all__ = ["AIAConfig", "process_aia_fits"]
