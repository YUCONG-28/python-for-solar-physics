"""Difference-image configuration helpers for AIA workflows.

English: Small helpers for fixed difference-image color limits.

中文：AIA 差分图固定色标范围相关的轻量辅助函数。
"""

from __future__ import annotations

import math

from .config import DIFF_CONFIG, AIAConfig

__all__ = ["diff_config_vlim", "resolve_fixed_difference_limits_for_wave"]


def diff_config_vlim(wave_val: int) -> float:
    config = DIFF_CONFIG.get(wave_val, {})
    vlim = float(config.get("vlim", 200.0))
    return vlim if math.isfinite(vlim) and vlim > 0 else 200.0


def resolve_fixed_difference_limits_for_wave(
    wave_val: int, cfg: AIAConfig
) -> tuple[float, float] | None:
    """Resolve explicit fixed limits using the historical runtime precedence."""
    vmin_by_wave = cfg.difference_vmin_by_wave or {}
    vmax_by_wave = cfg.difference_vmax_by_wave or {}
    vlim_by_wave = cfg.difference_vlim_by_wave or {}

    has_vmin = wave_val in vmin_by_wave
    has_vmax = wave_val in vmax_by_wave
    has_vlim = wave_val in vlim_by_wave

    if has_vmin or has_vmax:
        if has_vmin and has_vmax:
            return float(vmin_by_wave[wave_val]), float(vmax_by_wave[wave_val])
        if has_vmin:
            vlim = abs(float(vmin_by_wave[wave_val]))
            return -vlim, vlim
        vlim = abs(float(vmax_by_wave[wave_val]))
        return -vlim, vlim

    if has_vlim:
        vlim = abs(float(vlim_by_wave[wave_val]))
        return -vlim, vlim

    if cfg.difference_vmin is not None or cfg.difference_vmax is not None:
        if cfg.difference_vmin is not None and cfg.difference_vmax is not None:
            return float(cfg.difference_vmin), float(cfg.difference_vmax)
        if cfg.difference_vmin is not None:
            vlim = abs(float(cfg.difference_vmin))
            return -vlim, vlim
        vlim = abs(float(cfg.difference_vmax))
        return -vlim, vlim

    if cfg.difference_norm_mode == "fixed":
        raise ValueError(
            "difference_norm_mode='fixed' requires per-band limits, "
            "difference_vlim_by_wave, or global "
            "difference_vmin/difference_vmax."
        )
    return None


# Compatibility aliases matching the legacy implementation names.
_diff_config_vlim = diff_config_vlim
_resolve_fixed_difference_limits_for_wave = resolve_fixed_difference_limits_for_wave
