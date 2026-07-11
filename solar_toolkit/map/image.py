"""Array operations for map images.

English: Crop pixel-space regions of interest and normalize image arrays for
display.

中文：裁剪像素坐标中的感兴趣区域，并归一化图像数组以供显示。
"""

from __future__ import annotations

import numpy as np


def crop_roi(
    data: np.ndarray,
    *,
    x_range: tuple[int, int],
    y_range: tuple[int, int],
) -> np.ndarray:
    """Crop an array using pixel ``x`` and ``y`` half-open bounds."""

    array = np.asarray(data)
    x0, x1 = map(int, x_range)
    y0, y1 = map(int, y_range)
    return array[y0:y1, x0:x1]


def normalize_image(
    data: np.ndarray,
    *,
    vmin: float | None = None,
    vmax: float | None = None,
    clip: bool = True,
) -> np.ndarray:
    """Normalize an image to the 0..1 range."""

    array = np.asarray(data, dtype=float)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros_like(array, dtype=float)
    low = float(np.nanmin(finite) if vmin is None else vmin)
    high = float(np.nanmax(finite) if vmax is None else vmax)
    if high <= low:
        return np.zeros_like(array, dtype=float)
    normalized = (array - low) / (high - low)
    return np.clip(normalized, 0.0, 1.0) if clip else normalized


__all__ = ["crop_roi", "normalize_image"]
