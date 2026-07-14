"""Preview-only 2025-01-24 9-band raw radio source maps for RR+LL."""

from __future__ import annotations

from .radio_20250124_center_pm2min_9band_raw_base import build_event_config

__all__ = [
    "DRIFT_SELECTION_PRODUCT_CONFIG",
    "EVENT_CONFIG",
    "NEWKIRK_CONFIG",
    "NEWKIRK_HEIGHT_COMPARISON_CONFIG",
    "OUTPUT_CONFIG",
    "RADIO_DIAGNOSTIC_PRESENTATION_CONFIG",
    "USER_CONFIG",
]

EVENT_CONFIG = build_event_config(polarization="RR+LL", phase="preview")
USER_CONFIG = EVENT_CONFIG["user"]
OUTPUT_CONFIG = EVENT_CONFIG["output"]
NEWKIRK_CONFIG = EVENT_CONFIG["newkirk"]
NEWKIRK_HEIGHT_COMPARISON_CONFIG = EVENT_CONFIG["newkirk_height_comparison"]
DRIFT_SELECTION_PRODUCT_CONFIG = EVENT_CONFIG["drift_selection_products"]
RADIO_DIAGNOSTIC_PRESENTATION_CONFIG = EVENT_CONFIG["diagnostic_presentation"]
