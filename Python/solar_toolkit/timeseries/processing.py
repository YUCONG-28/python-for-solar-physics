"""Numerical processing for one-dimensional time series.

English: Apply a centered moving average and calculate shape-stable finite
differences.

中文：计算居中移动平均和平保持数组形状的有限差分。
"""

from __future__ import annotations

import numpy as np


def smooth_series(values, *, window_length: int = 5) -> np.ndarray:
    """Smooth values with a centered moving average and zero-padded edges."""

    window = max(1, int(window_length))
    if window % 2 == 0:
        window += 1
    array = np.asarray(values, dtype=float)
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(array, kernel, mode="same")


def derivative_series(values, *, spacing_seconds: float = 1.0) -> np.ndarray:
    """Return a shape-stable finite-difference derivative."""

    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return np.asarray([], dtype=float)
    if array.size == 1:
        return np.zeros_like(array, dtype=float)
    return np.gradient(array, float(spacing_seconds))


__all__ = ["derivative_series", "smooth_series"]
