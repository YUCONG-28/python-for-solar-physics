"""Compatibility config for the 2025-01-24 AIA/HMI/radio overlay.

The event configuration now lives with the main 2025-01-24 radio config. This
module keeps the historical config name importable without duplicating
event-specific science parameters.
"""

from __future__ import annotations

from .radio_20250124_config import AIA_RADIO_HMI_CONFIG

__all__ = ["AIA_RADIO_HMI_CONFIG"]
