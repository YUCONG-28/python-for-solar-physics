"""Pure coordinate helpers for FITS image display geometry.

The functions here do not read files, plot figures, or depend on local data.
They provide a tested baseline for future refactoring of radio FITS
``extent``/``origin`` handling.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

Extent = tuple[float, float, float, float]

__all__ = [
    "Extent",
    "calculate_fits_extent_from_header",
    "infer_image_origin_from_header",
    "normalize_radio_extent",
    "validate_extent_orientation",
]


def _header_float(header: Mapping[str, Any], key: str) -> float:
    try:
        return float(header[key])
    except KeyError as exc:
        raise KeyError(f"Missing FITS header keyword: {key}") from exc


def _resolve_image_shape(
    header: Mapping[str, Any], image_shape: Sequence[int] | None
) -> tuple[int, int]:
    if image_shape is not None:
        if len(image_shape) != 2:
            raise ValueError("image_shape must be a two-item sequence: (ny, nx)")
        ny, nx = int(image_shape[0]), int(image_shape[1])
    else:
        nx = int(_header_float(header, "NAXIS1"))
        ny = int(_header_float(header, "NAXIS2"))

    if nx <= 0 or ny <= 0:
        raise ValueError("image dimensions must be positive")
    return ny, nx


def calculate_fits_extent_from_header(
    header: Mapping[str, Any],
    image_shape: Sequence[int] | None = None,
    *,
    preserve_orientation: bool = True,
) -> Extent:
    """Return a matplotlib ``extent`` from FITS linear WCS keywords.

    The returned tuple uses matplotlib's standard order:
    ``(left, right, bottom, top)``.

    FITS ``CRPIX`` is interpreted as one-based, and the extent describes pixel
    edges. For example, row/column zero centers are half a pixel inside the
    returned extent.

    When ``preserve_orientation`` is true, the edge order keeps the sign of
    ``CDELT1`` and ``CDELT2``. Matplotlib accepts such inverted extents when the
    matching origin is chosen consistently. When false, x and y limits are
    sorted into increasing order.
    """

    ny, nx = _resolve_image_shape(header, image_shape)
    crval1 = _header_float(header, "CRVAL1")
    crpix1 = _header_float(header, "CRPIX1")
    cdelt1 = _header_float(header, "CDELT1")
    crval2 = _header_float(header, "CRVAL2")
    crpix2 = _header_float(header, "CRPIX2")
    cdelt2 = _header_float(header, "CDELT2")

    x_edge0 = crval1 + (0.5 - crpix1) * cdelt1
    x_edge1 = crval1 + (nx + 0.5 - crpix1) * cdelt1
    y_edge0 = crval2 + (0.5 - crpix2) * cdelt2
    y_edge1 = crval2 + (ny + 0.5 - crpix2) * cdelt2

    if preserve_orientation:
        return (float(x_edge0), float(x_edge1), float(y_edge0), float(y_edge1))

    left, right = sorted((float(x_edge0), float(x_edge1)))
    bottom, top = sorted((float(y_edge0), float(y_edge1)))
    return (left, right, bottom, top)


def infer_image_origin_from_header(
    header: Mapping[str, Any] | None = None,
    *,
    preserve_orientation: bool = True,
    mode: str = "auto",
) -> str:
    """Infer the matplotlib image origin for a radio FITS display.

    ``mode`` may be ``"upper"``, ``"lower"``, or ``"auto"``. The ``header`` is
    accepted for API symmetry and future validation; the current baseline
    mirrors the advanced radio script's rule:

    - preserved FITS orientation uses ``origin="lower"``;
    - normalized legacy display uses ``origin="upper"``.
    """

    _ = header
    normalized_mode = str(mode or "auto").lower()
    if normalized_mode in {"upper", "lower"}:
        return normalized_mode
    if normalized_mode != "auto":
        raise ValueError("mode must be 'auto', 'upper', or 'lower'")
    return "lower" if preserve_orientation else "upper"


def normalize_radio_extent(extent: Sequence[float]) -> Extent:
    """Return ``extent`` sorted into increasing x and y order."""

    if len(extent) != 4:
        raise ValueError("extent must contain four values")
    left, right, bottom, top = map(float, extent)
    x0, x1 = sorted((left, right))
    y0, y1 = sorted((bottom, top))
    return (x0, x1, y0, y1)


def validate_extent_orientation(extent: Sequence[float]) -> dict[str, bool]:
    """Describe whether an extent is normal or inverted on each axis."""

    if len(extent) != 4:
        raise ValueError("extent must contain four values")
    left, right, bottom, top = map(float, extent)
    x_increases = right > left
    y_increases = top > bottom
    return {
        "x_increases": x_increases,
        "y_increases": y_increases,
        "x_inverted": right < left,
        "y_inverted": top < bottom,
        "is_normalized": x_increases and y_increases,
    }
