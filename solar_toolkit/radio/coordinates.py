"""Neutral coordinate utilities for radio spatial diagnostics."""

from __future__ import annotations

import math

import numpy as np


def _finite(*values) -> bool:
    return bool(np.isfinite(np.asarray(values, dtype=float)).all())


def arcsec_to_rsun(x_arcsec, y_arcsec, solar_radius_arcsec):
    radius = float(solar_radius_arcsec) if _finite(solar_radius_arcsec) else np.nan
    if not np.isfinite(radius) or radius <= 0:
        return {
            "x_rsun": np.nan,
            "y_rsun": np.nan,
            "valid": False,
            "reason": "invalid_solar_radius_arcsec",
        }
    if not _finite(x_arcsec, y_arcsec):
        return {
            "x_rsun": np.nan,
            "y_rsun": np.nan,
            "valid": False,
            "reason": "nonfinite_arcsec_coordinate",
        }
    return {
        "x_rsun": float(x_arcsec) / radius,
        "y_rsun": float(y_arcsec) / radius,
        "valid": True,
        "reason": "ok",
    }


def rsun_to_arcsec(x_rsun, y_rsun, solar_radius_arcsec):
    radius = float(solar_radius_arcsec) if _finite(solar_radius_arcsec) else np.nan
    if not np.isfinite(radius) or radius <= 0:
        return {
            "x_arcsec": np.nan,
            "y_arcsec": np.nan,
            "valid": False,
            "reason": "invalid_solar_radius_arcsec",
        }
    if not _finite(x_rsun, y_rsun):
        return {
            "x_arcsec": np.nan,
            "y_arcsec": np.nan,
            "valid": False,
            "reason": "nonfinite_rsun_coordinate",
        }
    return {
        "x_arcsec": float(x_rsun) * radius,
        "y_arcsec": float(y_rsun) * radius,
        "valid": True,
        "reason": "ok",
    }


def compute_radial_unit_vector(x_rsun, y_rsun, min_radius=1e-6):
    if not _finite(x_rsun, y_rsun):
        return {
            "ux": np.nan,
            "uy": np.nan,
            "radius_rsun": np.nan,
            "valid": False,
            "reason": "nonfinite_rsun_coordinate",
        }
    radius = math.hypot(float(x_rsun), float(y_rsun))
    if radius < float(min_radius):
        return {
            "ux": np.nan,
            "uy": np.nan,
            "radius_rsun": radius,
            "valid": False,
            "reason": "anchor_too_close_to_disk_center",
        }
    return {
        "ux": float(x_rsun) / radius,
        "uy": float(y_rsun) / radius,
        "radius_rsun": radius,
        "valid": True,
        "reason": "ok",
    }


def validate_plot_extent_and_origin(extent, origin):
    if origin not in {"upper", "lower"}:
        return {"valid": False, "reason": "invalid_origin"}
    if extent is None or len(extent) != 4:
        return {"valid": False, "reason": "invalid_extent_length"}
    try:
        left, right, bottom, top = map(float, extent)
    except (TypeError, ValueError):
        return {"valid": False, "reason": "nonfinite_extent"}
    if not _finite(left, right, bottom, top):
        return {"valid": False, "reason": "nonfinite_extent"}
    if left == right or bottom == top:
        return {"valid": False, "reason": "degenerate_extent"}
    return {"valid": True, "reason": "ok"}


def normalize_roi_bounds_arcsec(source) -> dict[str, float]:
    """Return ROI bounds as left/bottom/right/top arcsec values."""
    bounds = _get_config_value(source, "roi_bounds_arcsec")
    if bounds is not None:
        if not isinstance(bounds, dict):
            raise ValueError("roi_bounds_arcsec must be a dict")
        missing = {"left", "bottom", "right", "top"} - set(bounds)
        if missing:
            raise ValueError(f"roi_bounds_arcsec missing keys: {sorted(missing)}")
        left = bounds["left"]
        bottom = bounds["bottom"]
        right = bounds["right"]
        top = bounds["top"]
    else:
        bottom_left = _get_config_value(source, "roi_bottom_left")
        top_right = _get_config_value(source, "roi_top_right")
        if bottom_left is None or top_right is None:
            raise ValueError(
                "ROI requires roi_bounds_arcsec or legacy roi_bottom_left/roi_top_right"
            )
        if len(bottom_left) != 2 or len(top_right) != 2:
            raise ValueError(
                "legacy ROI coordinates must be [x, y] pairs: "
                "roi_bottom_left=[left, bottom], roi_top_right=[right, top]"
            )
        left, bottom = bottom_left
        right, top = top_right

    try:
        normalized = {
            "left": float(left),
            "bottom": float(bottom),
            "right": float(right),
            "top": float(top),
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("ROI bounds must be finite numeric arcsec values") from exc

    if not _finite(*normalized.values()):
        raise ValueError("ROI bounds must be finite numeric arcsec values")
    if normalized["left"] >= normalized["right"]:
        raise ValueError("ROI bounds must satisfy left < right")
    if normalized["bottom"] >= normalized["top"]:
        raise ValueError("ROI bounds must satisfy bottom < top")
    return normalized


def _get_config_value(source, key: str, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def compute_position_residual(x1, y1, x2, y2):
    if not _finite(x1, y1, x2, y2):
        return {"residual": np.nan, "valid": False, "reason": "nonfinite_coordinate"}
    return {
        "residual": float(math.hypot(float(x1) - float(x2), float(y1) - float(y2))),
        "valid": True,
        "reason": "ok",
    }


def pixel_to_data_coord(
    x_pix, y_pix, extent, shape, origin="upper"
) -> tuple[float, float]:
    left, right, bottom, top = map(float, extent)
    ny, nx = shape
    dx = (right - left) / max(float(nx), 1.0)
    dy = (top - bottom) / max(float(ny), 1.0)
    x_arcsec = left + (float(x_pix) + 0.5) * dx
    if origin == "upper":
        y_arcsec = top - (float(y_pix) + 0.5) * dy
    elif origin == "lower":
        y_arcsec = bottom + (float(y_pix) + 0.5) * dy
    else:
        raise ValueError(f"Unsupported image origin: {origin}")
    return float(x_arcsec), float(y_arcsec)


def data_coord_to_pixel(
    x_arcsec, y_arcsec, extent, shape, origin="upper"
) -> tuple[float, float]:
    left, right, bottom, top = map(float, extent)
    ny, nx = shape
    dx = (right - left) / max(float(nx), 1.0)
    dy = (top - bottom) / max(float(ny), 1.0)
    x_pix = (float(x_arcsec) - left) / dx - 0.5
    if origin == "upper":
        y_pix = (top - float(y_arcsec)) / dy - 0.5
    elif origin == "lower":
        y_pix = (float(y_arcsec) - bottom) / dy - 0.5
    else:
        raise ValueError(f"Unsupported image origin: {origin}")
    return float(x_pix), float(y_pix)


def coordinate_roundtrip_error_pixel(
    x_pix, y_pix, extent, shape, origin="upper"
) -> float:
    x_arcsec, y_arcsec = pixel_to_data_coord(x_pix, y_pix, extent, shape, origin)
    x_back, y_back = data_coord_to_pixel(x_arcsec, y_arcsec, extent, shape, origin)
    return float(math.hypot(float(x_pix) - x_back, float(y_pix) - y_back))


def unravel_2d_index(
    flat_index: int | np.integer, shape: tuple[int, ...]
) -> tuple[int, int]:
    coords = np.asarray(np.unravel_index(int(flat_index), shape), dtype=np.intp)
    return int(coords[0]), int(coords[1])
