"""Difference-image configuration helpers for AIA workflows.

English: Small helpers for fixed difference-image color limits.

中文：AIA 差分图固定色标范围相关的轻量辅助函数。
"""

from __future__ import annotations

from .config import DIFF_CONFIG, AIAConfig


def diff_config_vlim(wave_val: int) -> float:
    config = DIFF_CONFIG.get(wave_val, {})
    return float(config.get("vlim", 250.0))


def resolve_fixed_difference_limits_for_wave(
    wave_val: int, cfg: AIAConfig
) -> tuple[float, float]:
    if cfg.difference_vmin is not None or cfg.difference_vmax is not None:
        vmin = cfg.difference_vmin
        vmax = cfg.difference_vmax
        if vmin is None:
            vmin = -float(vmax)
        if vmax is None:
            vmax = abs(float(vmin))
        return float(vmin), float(vmax)

    if wave_val in cfg.difference_vlim_by_wave:
        vlim = float(cfg.difference_vlim_by_wave[wave_val])
        return -vlim, vlim
    if (
        wave_val in cfg.difference_vmin_by_wave
        or wave_val in cfg.difference_vmax_by_wave
    ):
        vmin = cfg.difference_vmin_by_wave.get(wave_val)
        vmax = cfg.difference_vmax_by_wave.get(wave_val)
        if vmin is None:
            vmin = -abs(float(vmax))
        if vmax is None:
            vmax = abs(float(vmin))
        return float(vmin), float(vmax)

    vlim = diff_config_vlim(wave_val)
    return -vlim, vlim


# Compatibility aliases matching the legacy implementation names.
_diff_config_vlim = diff_config_vlim
_resolve_fixed_difference_limits_for_wave = resolve_fixed_difference_limits_for_wave
