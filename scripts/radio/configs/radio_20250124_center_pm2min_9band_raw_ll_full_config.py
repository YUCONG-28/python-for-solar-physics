"""Full-window 2025-01-24 9-band raw radio source maps for LL."""

from __future__ import annotations

from .radio_20250124_center_pm2min_9band_raw_base import build_event_config

EVENT_CONFIG = build_event_config(polarization="LL", phase="full")
USER_CONFIG = EVENT_CONFIG["user"]
OUTPUT_CONFIG = EVENT_CONFIG["output"]
NEWKIRK_CONFIG = EVENT_CONFIG["newkirk"]
NEWKIRK_HEIGHT_COMPARISON_CONFIG = EVENT_CONFIG["newkirk_height_comparison"]
DRIFT_SELECTION_PRODUCT_CONFIG = EVENT_CONFIG["drift_selection_products"]
RADIO_DIAGNOSTIC_PRESENTATION_CONFIG = EVENT_CONFIG["diagnostic_presentation"]
