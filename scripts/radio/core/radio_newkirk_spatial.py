"""Plane-of-sky Newkirk spatial projection for radio Gaussian diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .radio_coordinates import (
    arcsec_to_rsun,
    compute_position_residual,
    compute_radial_unit_vector,
    rsun_to_arcsec,
)
from .radio_io import parse_datetime_value, truthy
from .radio_newkirk_extrapolation import (
    newkirk_radius_from_frequency_mhz,
    plasma_density_from_frequency_mhz,
)


def build_newkirk_spatial_dataframe(gaussian_df, config):
    cfg = dict(config or {})
    df = pd.DataFrame(gaussian_df).copy()
    if df.empty:
        return pd.DataFrame(columns=_SPATIAL_COLUMNS)

    solar_radius = _solar_radius_arcsec(cfg)
    harmonic = cfg.get("harmonic", cfg.get("newkirk_harmonic", 1))
    multiplier = cfg.get("newkirk_multiplier", cfg.get("multiplier", 1.0))
    rows = []
    for _, row in df.iterrows():
        projected = project_newkirk_radius_from_gaussian_anchor(
            row,
            solar_radius_arcsec=solar_radius,
            harmonic=harmonic,
            newkirk_multiplier=multiplier,
        )
        out = {
            "time": row.get("time", ""),
            "frequency_mhz": _row_frequency(row),
            "source_type": classify_source_type(row, cfg),
            "gaussian_x_arcsec": _float_or_nan(row.get("center_x_arcsec")),
            "gaussian_y_arcsec": _float_or_nan(row.get("center_y_arcsec")),
            "gaussian_fwhm_major_arcsec": _first_number(
                row,
                ["fwhm_major_arcsec", "fwhm_width_arcsec", "fwhm_x_arcsec"],
            ),
            "gaussian_fwhm_minor_arcsec": _first_number(
                row,
                ["fwhm_minor_arcsec", "fwhm_height_arcsec", "fwhm_y_arcsec"],
            ),
            "gaussian_angle_deg": _angle_deg(row),
            "gaussian_fit_success": _gaussian_fit_success(row),
            "gaussian_quality_flag": str(row.get("quality_flag", "")),
        }
        out.update(projected)
        if not out["gaussian_fit_success"]:
            out["geometry_valid"] = False
            out["geometry_reason"] = "invalid_gaussian_fit"
        out.update(compute_gaussian_newkirk_residuals({**out, **projected}))
        rows.append(out)

    result = pd.DataFrame(rows)
    for column in _SPATIAL_COLUMNS:
        if column not in result.columns:
            result[column] = np.nan
    return result[_SPATIAL_COLUMNS]


def classify_source_type(row, config):
    for key in ("source_type", "burst_type", "type"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    time_value = parse_datetime_value(row.get("time"))
    freq = _row_frequency(row)
    if _matches_window_and_frequency(
        time_value,
        freq,
        config.get("TYPEIII_TIME_WINDOWS", []),
        config.get("TYPEIII_FREQ_RANGE"),
    ):
        return "typeIII"
    if _matches_window_and_frequency(
        time_value,
        freq,
        config.get("SPIKE_TIME_WINDOWS", []),
        config.get("SPIKE_FREQ_RANGE"),
    ):
        return "spike"
    return "unknown"


def project_newkirk_radius_from_gaussian_anchor(
    row, solar_radius_arcsec, harmonic, newkirk_multiplier
):
    freq = _row_frequency(row)
    density = _safe_physics_value(
        plasma_density_from_frequency_mhz, freq, harmonic=harmonic
    )
    radius = _safe_physics_value(
        newkirk_radius_from_frequency_mhz,
        freq,
        multiplier=newkirk_multiplier,
        harmonic=harmonic,
    )
    gauss_arcsec = arcsec_to_rsun(
        row.get("center_x_arcsec"),
        row.get("center_y_arcsec"),
        solar_radius_arcsec,
    )
    out = {
        "gaussian_x_rsun": gauss_arcsec["x_rsun"],
        "gaussian_y_rsun": gauss_arcsec["y_rsun"],
        "newkirk_density_cm3": density,
        "newkirk_radius_rsun": radius,
        "newkirk_height_rsun": radius - 1.0 if np.isfinite(radius) else np.nan,
        "newkirk_x_rsun": np.nan,
        "newkirk_y_rsun": np.nan,
        "newkirk_x_arcsec": np.nan,
        "newkirk_y_arcsec": np.nan,
        "harmonic": harmonic,
        "newkirk_multiplier": float(newkirk_multiplier),
        "geometry_valid": False,
        "geometry_reason": "ok",
    }
    if not gauss_arcsec["valid"]:
        out["geometry_reason"] = gauss_arcsec["reason"]
        return out
    if not np.isfinite(radius):
        out["geometry_reason"] = "invalid_newkirk_inversion"
        return out
    unit = compute_radial_unit_vector(
        gauss_arcsec["x_rsun"],
        gauss_arcsec["y_rsun"],
    )
    if not unit["valid"]:
        out["geometry_reason"] = unit["reason"]
        return out

    out["newkirk_x_rsun"] = unit["ux"] * radius
    out["newkirk_y_rsun"] = unit["uy"] * radius
    arcsec = rsun_to_arcsec(
        out["newkirk_x_rsun"], out["newkirk_y_rsun"], solar_radius_arcsec
    )
    out["newkirk_x_arcsec"] = arcsec["x_arcsec"]
    out["newkirk_y_arcsec"] = arcsec["y_arcsec"]
    out["geometry_valid"] = bool(arcsec["valid"])
    out["geometry_reason"] = arcsec["reason"]
    return out


def compute_gaussian_newkirk_residuals(row):
    residual_rsun = compute_position_residual(
        row.get("gaussian_x_rsun"),
        row.get("gaussian_y_rsun"),
        row.get("newkirk_x_rsun"),
        row.get("newkirk_y_rsun"),
    )
    residual_arcsec = compute_position_residual(
        row.get("gaussian_x_arcsec"),
        row.get("gaussian_y_arcsec"),
        row.get("newkirk_x_arcsec"),
        row.get("newkirk_y_arcsec"),
    )
    return {
        "residual_rsun": residual_rsun["residual"],
        "residual_arcsec": residual_arcsec["residual"],
    }


def _matches_window_and_frequency(time_value, freq, windows, freq_range) -> bool:
    if not windows and freq_range is None:
        return False
    time_ok = not windows or any(
        _time_in_window(time_value, window) for window in windows
    )
    freq_ok = _frequency_in_range(freq, freq_range)
    return bool(time_ok and freq_ok)


def _time_in_window(value, window) -> bool:
    if value is None or not window:
        return False
    if isinstance(window, dict):
        start = parse_datetime_value(window.get("start"))
        end = parse_datetime_value(window.get("end"))
    else:
        start = parse_datetime_value(window[0]) if len(window) >= 1 else None
        end = parse_datetime_value(window[1]) if len(window) >= 2 else None
    if start is None or end is None:
        return False
    if end < start:
        start, end = end, start
    return start <= value <= end


def _frequency_in_range(freq, freq_range) -> bool:
    if freq_range is None:
        return True
    if not np.isfinite(freq):
        return False
    lo, hi = map(float, freq_range)
    if lo > hi:
        lo, hi = hi, lo
    return lo <= float(freq) <= hi


def _solar_radius_arcsec(config) -> float:
    value = config.get("solar_radius_arcsec")
    if value is None or not np.isfinite(_float_or_nan(value)) or float(value) <= 0:
        return 959.63
    return float(value)


def _row_frequency(row) -> float:
    for key in ("frequency_mhz", "freq_mhz", "freq"):
        value = row.get(key)
        numeric = _float_or_nan(value)
        if np.isfinite(numeric):
            return numeric
    return np.nan


def _first_number(row, keys) -> float:
    for key in keys:
        value = _float_or_nan(row.get(key))
        if np.isfinite(value):
            return value
    return np.nan


def _angle_deg(row) -> float:
    deg = _float_or_nan(row.get("gaussian_angle_deg"))
    if np.isfinite(deg):
        return deg
    theta = _float_or_nan(row.get("theta_rad"))
    return float(np.degrees(theta)) if np.isfinite(theta) else np.nan


def _gaussian_fit_success(row) -> bool:
    flag = str(row.get("quality_flag", "")).strip().lower()
    overlay = row.get("overlay_valid", True)
    trajectory = row.get("trajectory_valid", True)
    return bool(flag in {"ok", ""} and truthy(overlay) and truthy(trajectory))


def _safe_physics_value(func, *args, **kwargs) -> float:
    try:
        value = func(*args, **kwargs)
    except Exception:
        return np.nan
    return _float_or_nan(value)


def _float_or_nan(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


_SPATIAL_COLUMNS = [
    "time",
    "frequency_mhz",
    "source_type",
    "gaussian_x_arcsec",
    "gaussian_y_arcsec",
    "gaussian_x_rsun",
    "gaussian_y_rsun",
    "gaussian_fwhm_major_arcsec",
    "gaussian_fwhm_minor_arcsec",
    "gaussian_angle_deg",
    "newkirk_density_cm3",
    "newkirk_radius_rsun",
    "newkirk_height_rsun",
    "newkirk_x_rsun",
    "newkirk_y_rsun",
    "newkirk_x_arcsec",
    "newkirk_y_arcsec",
    "residual_rsun",
    "residual_arcsec",
    "harmonic",
    "newkirk_multiplier",
    "geometry_valid",
    "geometry_reason",
    "gaussian_fit_success",
    "gaussian_quality_flag",
]
