"""Template radio configuration for a future 2025-05-03 event pass."""

from __future__ import annotations

import copy

from .radio_20250124_config import NEWKIRK_CONFIG as _BASE_NEWKIRK_CONFIG
from .radio_20250124_config import USER_CONFIG as _BASE_USER_CONFIG

USER_CONFIG = copy.deepcopy(_BASE_USER_CONFIG)
USER_CONFIG["data"].update(
    {
        "multi_band_root": r"TODO:\path\to\20250503\radio\multi_band_root",
        "single_file_path": r"TODO:\path\to\20250503\radio\single_file.fits",
        "data_dir": r"TODO:\path\to\20250503\radio\data_dir",
        "start_idx": 0,
        "end_idx": 0,
    }
)
USER_CONFIG["spectrogram"].update(
    {
        "file_paths": [
            r"TODO:\path\to\20250503\spectrogram_part1.fits",
            r"TODO:\path\to\20250503\spectrogram_part2.fits",
        ],
        "file_path": r"TODO:\path\to\20250503\spectrogram.fits",
        "time_start": "TODO:2025-05-03T00:00:00",
        "time_end": "TODO:2025-05-03T00:00:30",
    }
)
USER_CONFIG["output"]["output_dir"] = r"TODO:\path\to\20250503\outputs"

NEWKIRK_CONFIG = copy.deepcopy(_BASE_NEWKIRK_CONFIG)
