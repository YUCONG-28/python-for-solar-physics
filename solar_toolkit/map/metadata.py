"""Metadata helpers for SunPy-compatible maps and FITS headers.

English: Resolve observation times and display extents from map-like objects or
metadata mappings.

中文：从类 Map 对象或元数据映射中解析观测时间和显示范围。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from solar_toolkit.time import parse_time

from .coordinates import calculate_fits_extent_from_header


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


__all__ = ["get_display_extent", "get_map_obs_time"]
