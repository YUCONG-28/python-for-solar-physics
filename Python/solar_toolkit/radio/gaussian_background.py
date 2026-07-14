"""Background and noise-estimation helpers for radio Gaussian fitting."""

from __future__ import annotations

import numpy as np

__all__ = ["_safe_rms_map", "estimate_background_noise"]


def estimate_background_noise(data, source_exclusion_mask=None):
    work = np.asarray(data, dtype=np.float64)
    valid_mask = np.isfinite(work)
    if source_exclusion_mask is not None:
        valid_mask &= ~source_exclusion_mask
    finite_data = work[valid_mask]
    if finite_data.size == 0:
        return np.nan, np.nan
    background_level = float(np.nanmedian(finite_data))
    mad = float(np.nanmedian(np.abs(finite_data - background_level)))
    noise_sigma = 1.4826 * mad
    if not np.isfinite(noise_sigma) or noise_sigma <= 0:
        noise_sigma = float(np.nanstd(finite_data))
    return background_level, noise_sigma


def _safe_rms_map(rms_map):
    safe = np.asarray(rms_map, dtype=np.float64).copy()
    finite_positive = safe[np.isfinite(safe) & (safe > 0)]
    fallback = float(np.nanmedian(finite_positive)) if finite_positive.size else 1.0
    if not np.isfinite(fallback) or fallback <= 0:
        fallback = 1.0
    safe[~np.isfinite(safe) | (safe <= 0)] = fallback
    return safe
