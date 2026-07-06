"""Map-oriented helpers built around SunPy-compatible metadata.

English: Thin utilities for display extent, observation time, ROI cropping, and
normalization. They do not replace ``sunpy.map.Map``.

中文: 围绕 SunPy Map/类 FITS header 的显示范围、观测时间、ROI 裁剪和归一化
轻量工具, 不替代 ``sunpy.map.Map``。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from solar_toolkit.coordinates import calculate_fits_extent_from_header
from solar_toolkit.time import parse_time


def get_map_obs_time(map_or_header: Any):
    """Return observation time from a SunPy Map-like object or header."""

    if hasattr(map_or_header, "date") and map_or_header.date is not None:
        return parse_time(str(map_or_header.date.isot))
    header = _header_from(map_or_header)
    for key in ("DATE-OBS", "DATE_OBS", "date-obs", "date_obs"):
        if key in header:
            return parse_time(header[key])
    raise KeyError("Missing DATE-OBS/DATE_OBS metadata")


def get_display_extent(
    map_or_header: Any,
    image_shape: Sequence[int] | None = None,
    *,
    preserve_orientation: bool = True,
) -> tuple[float, float, float, float]:
    """Return a matplotlib extent from a Map-like object or FITS header."""

    if hasattr(map_or_header, "meta"):
        header = map_or_header.meta
        if image_shape is None and hasattr(map_or_header, "data"):
            image_shape = np.asarray(map_or_header.data).shape[-2:]
    else:
        header = _header_from(map_or_header)
    return calculate_fits_extent_from_header(
        header,
        image_shape=image_shape,
        preserve_orientation=preserve_orientation,
    )


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


def _header_from(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "header"):
        return value.header
    if hasattr(value, "meta"):
        return value.meta
    raise TypeError(
        "Expected a mapping, FITS HDU/header-like object, or SunPy Map-like object"
    )


__all__ = [
    "crop_roi",
    "get_display_extent",
    "get_map_obs_time",
    "normalize_image",
]
