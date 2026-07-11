"""Mosaic layout helpers for AIA workflows.

English: Layout and wavelength-slot helpers for multi-band AIA panels.

中文：AIA 多波段拼图的布局和波段槽位选择辅助函数。
"""

from __future__ import annotations

import math
from pathlib import Path

from .config import AIAConfig
from .io import discover_wavelength_dirs

__all__ = [
    "auto_mosaic_ncols",
    "layout_grid",
    "layout_mosaic_grid",
    "mosaic_slot_wavelengths",
    "ordered_unique",
]


def layout_grid(n: int) -> tuple[int, int]:
    if n <= 0:
        return 1, 1
    ncol = max(1, math.ceil(math.sqrt(n)))
    nrow = max(1, math.ceil(n / ncol))
    return nrow, ncol


def auto_mosaic_ncols(n: int) -> int:
    if n <= 0:
        return 1
    if n == 3:
        return 3
    if n == 4:
        return 2
    if n == 5:
        return 3
    if n == 6:
        return 3
    if n == 7:
        return 4
    if n == 8:
        return 4
    return math.ceil(math.sqrt(n))


def layout_mosaic_grid(n: int, mosaic_ncols: int | None = None) -> tuple[int, int]:
    if n <= 0:
        return 1, 1
    if mosaic_ncols is not None:
        if mosaic_ncols <= 0:
            raise ValueError("mosaic_ncols must be a positive integer or None.")
        ncol = min(mosaic_ncols, n)
        nrow = math.ceil(n / ncol)
        return nrow, ncol
    ncol = auto_mosaic_ncols(n)
    nrow = math.ceil(n / ncol)
    return nrow, ncol


def ordered_unique(values) -> tuple[int, ...]:
    seen = set()
    ordered = []
    for value in values:
        int_value = int(value)
        if int_value not in seen:
            seen.add(int_value)
            ordered.append(int_value)
    return tuple(ordered)


def mosaic_slot_wavelengths(cfg: AIAConfig) -> tuple[int, ...]:
    data_path = Path(cfg.data_path)
    original_waves = cfg.multi_band_wavelengths
    if original_waves is None:
        original_waves = discover_wavelength_dirs(data_path)
    if cfg.mosaic_difference_inline and cfg.draw_difference:
        diff_waves = cfg.difference_wavelengths or original_waves
        if cfg.draw_original:
            return ordered_unique(tuple(original_waves) + tuple(diff_waves))
        return ordered_unique(diff_waves)
    return tuple(original_waves)


# Compatibility aliases matching the legacy implementation names.
_layout_grid = layout_grid
_auto_mosaic_ncols = auto_mosaic_ncols
_layout_mosaic_grid = layout_mosaic_grid
_ordered_unique = ordered_unique
_mosaic_slot_wavelengths = mosaic_slot_wavelengths
