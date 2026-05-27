"""Gaussian projected-height versus Newkirk radial-height diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .radio_io import parse_datetime_value, truthy
from .radio_newkirk_extrapolation import (
    newkirk_radius_from_frequency_mhz,
    plasma_density_from_frequency_mhz,
)
from .radio_newkirk_spatial import classify_source_type


DEFAULT_SELECTED_MODELS = [
    {"multiplier": 1.0, "harmonic": 1},
    {"multiplier": 1.0, "harmonic": 2},
    {"multiplier": 2.0, "harmonic": 1},
    {"multiplier": 2.0, "harmonic": 2},
    {"multiplier": 4.0, "harmonic": 1},
    {"multiplier": 4.0, "harmonic": 2},
]


def compute_gaussian_projected_height(x_arcsec, y_arcsec, solar_radius_arcsec):
    radius = _float_or_nan(solar_radius_arcsec)
    if not np.isfinite(radius) or radius <= 0:
        return {
            "gaussian_rho_rsun": np.nan,
            "gaussian_height_rsun": np.nan,
            "height_valid": False,
            "height_invalid_reason": "invalid_solar_radius_arcsec",
        }

    x = _float_or_nan(x_arcsec)
    y = _float_or_nan(y_arcsec)
    if not np.isfinite(x) or not np.isfinite(y):
        return {
            "gaussian_rho_rsun": np.nan,
            "gaussian_height_rsun": np.nan,
            "height_valid": False,
            "height_invalid_reason": "nonfinite_projected_coordinate",
        }

    rho = float(np.hypot(x, y) / radius)
    height = rho - 1.0
    if rho < 1.0:
        return {
            "gaussian_rho_rsun": rho,
            "gaussian_height_rsun": height,
            "height_valid": False,
            "height_invalid_reason": "inside_disk_projected_distance_only",
        }
    return {
        "gaussian_rho_rsun": rho,
        "gaussian_height_rsun": height,
        "height_valid": True,
        "height_invalid_reason": "ok",
    }


def build_gaussian_newkirk_height_table(gaussian_df, config):
    cfg = dict(config or {})
    df = pd.DataFrame(gaussian_df).copy()
    if df.empty:
        return pd.DataFrame(columns=HEIGHT_COLUMNS)
    if cfg.get("drift_selections"):
        from .radio_frequency_priority_diagnostics import (
            apply_frequency_priority_drift_matching,
        )

        df = apply_frequency_priority_drift_matching(
            df,
            pd.DataFrame(cfg.get("drift_selections") or []),
            cfg,
        )

    solar_radius = _solar_radius_arcsec(cfg)
    rows = []
    for _, row in df.iterrows():
        freq = _row_frequency(row)
        drift_match = {
            "drift_label": _text_or_empty(row.get("drift_label")),
            "source_type": _text_or_empty(row.get("source_type")),
            "warning": _text_or_empty(row.get("drift_match_warning")),
        }
        if not drift_match["drift_label"] and not cfg.get("drift_selections"):
            drift_match.update(_match_drift_selection(row, freq, cfg))
        source_type = classify_source_type(row, cfg)
        if drift_match["source_type"] and source_type == "unknown":
            source_type = drift_match["source_type"]
        projected = compute_gaussian_projected_height(
            row.get("center_x_arcsec"),
            row.get("center_y_arcsec"),
            solar_radius,
        )
        gaussian_fit_success = _gaussian_fit_success(row)
        if not gaussian_fit_success and projected["height_invalid_reason"] == "ok":
            projected["height_valid"] = False
            projected["height_invalid_reason"] = "invalid_gaussian_fit"

        for model in _selected_models(cfg):
            multiplier = float(model.get("multiplier", model.get("newkirk_multiplier", 1.0)))
            harmonic = model.get("harmonic", 1)
            density = _safe_physics_value(
                plasma_density_from_frequency_mhz, freq, harmonic=harmonic
            )
            radius = _safe_physics_value(
                newkirk_radius_from_frequency_mhz,
                freq,
                multiplier=multiplier,
                harmonic=harmonic,
            )
            newkirk_height = radius - 1.0 if np.isfinite(radius) else np.nan
            reason = projected["height_invalid_reason"]
            height_valid = bool(projected["height_valid"])
            if not np.isfinite(radius):
                height_valid = False
                reason = _append_reason(reason, "invalid_newkirk_inversion")

            residual = (
                projected["gaussian_height_rsun"] - newkirk_height
                if np.isfinite(projected["gaussian_height_rsun"])
                and np.isfinite(newkirk_height)
                else np.nan
            )
            ratio = (
                projected["gaussian_height_rsun"] / newkirk_height
                if np.isfinite(projected["gaussian_height_rsun"])
                and np.isfinite(newkirk_height)
                and newkirk_height != 0
                else np.nan
            )
            rows.append(
                {
                    "time": row.get("time", ""),
                    "frequency_mhz": freq,
                    "source_type": source_type,
                    "drift_label": drift_match["drift_label"],
                    "drift_match_warning": drift_match.get("warning", ""),
                    "gaussian_x_arcsec": _float_or_nan(row.get("center_x_arcsec")),
                    "gaussian_y_arcsec": _float_or_nan(row.get("center_y_arcsec")),
                    "solar_radius_arcsec": solar_radius,
                    "gaussian_rho_rsun": projected["gaussian_rho_rsun"],
                    "gaussian_height_rsun": projected["gaussian_height_rsun"],
                    "newkirk_multiplier": multiplier,
                    "harmonic": harmonic,
                    "electron_density_cm3": density,
                    "newkirk_radius_rsun": radius,
                    "newkirk_height_rsun": newkirk_height,
                    "height_residual_rsun": residual,
                    "height_residual_arcsec": residual * solar_radius if np.isfinite(residual) else np.nan,
                    "height_ratio_gauss_to_newkirk": ratio,
                    "gaussian_fit_success": gaussian_fit_success,
                    "gaussian_quality_flag": str(row.get("quality_flag", "")),
                    "height_valid": height_valid,
                    "height_invalid_reason": reason,
                }
            )

    out = pd.DataFrame(rows)
    for column in HEIGHT_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    return out[HEIGHT_COLUMNS]


def model_label(multiplier, harmonic) -> str:
    return f"{float(multiplier):g}× Newkirk, s={float(harmonic):g}"


def _selected_models(config):
    models = config.get("selected_models") or DEFAULT_SELECTED_MODELS
    normalized = []
    for model in models:
        if not isinstance(model, dict):
            continue
        normalized.append(
            {
                "multiplier": float(model.get("multiplier", model.get("newkirk_multiplier", 1.0))),
                "harmonic": model.get("harmonic", 1),
            }
        )
    return normalized or list(DEFAULT_SELECTED_MODELS)


def _solar_radius_arcsec(config) -> float:
    value = config.get("solar_radius_arcsec")
    if value is None or not np.isfinite(_float_or_nan(value)) or float(value) <= 0:
        return 959.63
    return float(value)


def _row_frequency(row) -> float:
    for key in ("frequency_mhz", "freq_mhz", "freq"):
        value = _float_or_nan(row.get(key))
        if np.isfinite(value):
            return value
    return np.nan


def _gaussian_fit_success(row) -> bool:
    flag = str(row.get("quality_flag", "")).strip().lower()
    overlay = row.get("overlay_valid", True)
    trajectory = row.get("trajectory_valid", True)
    return bool(flag in {"ok", ""} and truthy(overlay) and truthy(trajectory))


def _match_drift_selection(row, frequency_mhz: float, config: dict) -> dict:
    selections = config.get("drift_selections") or []
    if isinstance(selections, pd.DataFrame):
        selections = selections.to_dict("records")
    if not selections:
        return {"drift_label": "", "source_type": ""}
    row_time = parse_datetime_value(row.get("time"))
    if row_time is None or not np.isfinite(frequency_mhz):
        return {"drift_label": "", "source_type": ""}
    time_tol = float(config.get("drift_time_tolerance_s", 1.0) or 0.0)
    raw_freq_tol = config.get("drift_frequency_tolerance_mhz", 5.0)
    if isinstance(raw_freq_tol, str):
        from .radio_frequency_priority_diagnostics import (
            resolve_comparison_frequencies,
            resolve_drift_frequency_tolerance,
        )

        freq_tol = resolve_drift_frequency_tolerance(
            config, resolve_comparison_frequencies(config)
        )
    else:
        freq_tol = float(raw_freq_tol or 0.0)
    best = None
    best_delta = np.inf
    for selection in selections:
        if not isinstance(selection, dict):
            continue
        expected = _frequency_on_drift_selection(row_time, selection, time_tol)
        if expected is None or not np.isfinite(expected):
            continue
        delta = abs(float(frequency_mhz) - expected)
        if delta <= freq_tol and delta < best_delta:
            best = selection
            best_delta = delta
    if best is None:
        return {"drift_label": "", "source_type": ""}
    return {
        "drift_label": _text_or_empty(best.get("label")),
        "source_type": _source_type_from_selection(best),
    }


def _frequency_on_drift_selection(row_time, selection: dict, time_tolerance_s: float):
    t_start = parse_datetime_value(selection.get("t_start"))
    t_end = parse_datetime_value(selection.get("t_end"))
    f_start = _float_or_nan(selection.get("f_start_mhz"))
    f_end = _float_or_nan(selection.get("f_end_mhz"))
    if (
        t_start is None
        or t_end is None
        or not np.isfinite(f_start)
        or not np.isfinite(f_end)
    ):
        return None
    if t_end < t_start:
        t_start, t_end = t_end, t_start
        f_start, f_end = f_end, f_start
    total = (t_end - t_start).total_seconds()
    offset = (row_time - t_start).total_seconds()
    if offset < -time_tolerance_s or offset > total + time_tolerance_s:
        return None
    if abs(total) <= 1e-12:
        return 0.5 * (f_start + f_end)
    fraction = min(1.0, max(0.0, offset / total))
    return f_start + fraction * (f_end - f_start)


def _source_type_from_selection(selection: dict) -> str:
    for key in ("source_type", "burst_type", "type"):
        value = _text_or_empty(selection.get(key))
        if value:
            return value
    return ""


def _text_or_empty(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _safe_physics_value(func, *args, **kwargs) -> float:
    try:
        return _float_or_nan(func(*args, **kwargs))
    except Exception:
        return np.nan


def _append_reason(existing: str, reason: str) -> str:
    if not existing or existing == "ok":
        return reason
    if reason in str(existing).split(";"):
        return str(existing)
    return f"{existing};{reason}"


def _float_or_nan(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


HEIGHT_COLUMNS = [
    "time",
    "frequency_mhz",
    "source_type",
    "drift_label",
    "drift_match_warning",
    "gaussian_x_arcsec",
    "gaussian_y_arcsec",
    "solar_radius_arcsec",
    "gaussian_rho_rsun",
    "gaussian_height_rsun",
    "newkirk_multiplier",
    "harmonic",
    "electron_density_cm3",
    "newkirk_radius_rsun",
    "newkirk_height_rsun",
    "height_residual_rsun",
    "height_residual_arcsec",
    "height_ratio_gauss_to_newkirk",
    "gaussian_fit_success",
    "gaussian_quality_flag",
    "height_valid",
    "height_invalid_reason",
]
