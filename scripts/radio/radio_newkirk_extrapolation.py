"""Newkirk density-model extrapolation for radio Gaussian and drift diagnostics."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

RSUN_KM = 695_700.0
NEWKIRK_BASE_DENSITY_CM3 = 4.2e4
NEWKIRK_EXPONENT = 4.32
PLASMA_FREQ_COEFF_KHZ = 8.98


def plasma_density_from_frequency_mhz(freq_mhz, harmonic=1):
    freq = np.asarray(freq_mhz, dtype=np.float64)
    harmonic = float(harmonic)
    if harmonic <= 0:
        raise ValueError("harmonic must be positive")
    density = (1000.0 * freq / (PLASMA_FREQ_COEFF_KHZ * harmonic)) ** 2
    return _scalar_or_array(density)


def newkirk_density_cm3(r_rsun, multiplier=1.0):
    r = np.asarray(r_rsun, dtype=np.float64)
    multiplier = float(multiplier)
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")
    density = multiplier * NEWKIRK_BASE_DENSITY_CM3 * 10.0 ** (
        NEWKIRK_EXPONENT / r
    )
    return _scalar_or_array(density)


def newkirk_radius_from_density(ne_cm3, multiplier=1.0):
    ne = np.asarray(ne_cm3, dtype=np.float64)
    multiplier = float(multiplier)
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = np.log10(ne / (multiplier * NEWKIRK_BASE_DENSITY_CM3))
        radius = NEWKIRK_EXPONENT / denom
    radius = np.where(
        (ne > multiplier * NEWKIRK_BASE_DENSITY_CM3) & np.isfinite(radius),
        radius,
        np.nan,
    )
    return _scalar_or_array(radius)


def newkirk_radius_from_frequency_mhz(freq_mhz, multiplier=1.0, harmonic=1):
    density = plasma_density_from_frequency_mhz(freq_mhz, harmonic=harmonic)
    return newkirk_radius_from_density(density, multiplier=multiplier)


def newkirk_height_from_frequency_mhz(freq_mhz, multiplier=1.0, harmonic=1):
    radius = np.asarray(
        newkirk_radius_from_frequency_mhz(
            freq_mhz, multiplier=multiplier, harmonic=harmonic
        ),
        dtype=np.float64,
    )
    return _scalar_or_array(radius - 1.0)


def newkirk_speed_from_drift_rate(freq_mhz, drift_rate_mhz_s, r_rsun):
    freq = float(freq_mhz)
    drift = float(drift_rate_mhz_s)
    radius = float(r_rsun)
    if freq <= 0 or radius <= 0 or not np.isfinite([freq, drift, radius]).all():
        dr_dt = np.nan
    else:
        dr_dt = -(drift / freq) * radius**2 / (2.16 * math.log(10.0))
    return {
        "frequency_mhz": freq,
        "drift_rate_mhz_s": drift,
        "r_rsun": radius,
        "dr_dt_rsun_s": float(dr_dt) if np.isfinite(dr_dt) else np.nan,
        "speed_km_s": float(dr_dt * RSUN_KM) if np.isfinite(dr_dt) else np.nan,
    }


def attach_newkirk_height_to_gaussian(
    df,
    multiplier,
    harmonic,
    solar_radius_arcsec,
    los_sign,
):
    data = _valid_gaussian_rows(pd.DataFrame(df).copy())
    if data.empty:
        return data

    freq = pd.to_numeric(data["freq"], errors="coerce")
    r_model = np.asarray(
        newkirk_radius_from_frequency_mhz(
            freq.to_numpy(dtype=float), multiplier=multiplier, harmonic=harmonic
        ),
        dtype=float,
    )
    x_arcsec = pd.to_numeric(data["center_x_arcsec"], errors="coerce").to_numpy(
        dtype=float
    )
    y_arcsec = pd.to_numeric(data["center_y_arcsec"], errors="coerce").to_numpy(
        dtype=float
    )
    projected_r = np.sqrt(x_arcsec**2 + y_arcsec**2) / float(solar_radius_arcsec)
    z_squared = r_model**2 - projected_r**2
    z_rsun = float(los_sign) * np.sqrt(np.where(z_squared >= 0, z_squared, np.nan))

    data["newkirk_multiplier"] = float(multiplier)
    data["newkirk_harmonic"] = (
        int(harmonic) if float(harmonic).is_integer() else float(harmonic)
    )
    data["newkirk_density_cm3"] = plasma_density_from_frequency_mhz(
        freq.to_numpy(dtype=float), harmonic=harmonic
    )
    data["newkirk_r_rsun"] = r_model
    data["newkirk_height_rsun"] = r_model - 1.0
    data["projected_r_rsun"] = projected_r
    data["newkirk_z_rsun"] = z_rsun
    data["newkirk_z_arcsec"] = z_rsun * float(solar_radius_arcsec)
    return data[np.isfinite(data["newkirk_r_rsun"])].reset_index(drop=True)


def extrapolate_drift_line_with_newkirk(drift_row, multiplier, harmonic):
    row = dict(drift_row)
    f_start = float(row.get("f_start_mhz", np.nan))
    f_end = float(row.get("f_end_mhz", np.nan))
    drift = float(row.get("drift_rate_mhz_s", np.nan))
    mid_freq = float(np.nanmean([f_start, f_end]))
    radius = float(
        newkirk_radius_from_frequency_mhz(
            mid_freq, multiplier=multiplier, harmonic=harmonic
        )
    )
    speed = newkirk_speed_from_drift_rate(mid_freq, drift, radius)
    out = dict(row)
    out.update(
        {
            "newkirk_multiplier": float(multiplier),
            "newkirk_harmonic": int(harmonic)
            if float(harmonic).is_integer()
            else float(harmonic),
            "mid_frequency_mhz": mid_freq,
            "newkirk_r_rsun": radius,
            "newkirk_height_rsun": radius - 1.0
            if np.isfinite(radius)
            else np.nan,
            "dr_dt_rsun_s": speed["dr_dt_rsun_s"],
            "speed_km_s": speed["speed_km_s"],
        }
    )
    return out


def _valid_gaussian_rows(df: pd.DataFrame) -> pd.DataFrame:
    required = {"quality_flag", "overlay_valid", "trajectory_valid"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"Gaussian diagnostics missing required columns: {sorted(missing)}"
        )
    mask = (
        df["quality_flag"].astype(str).str.lower().eq("ok")
        & df["overlay_valid"].map(_truthy)
        & df["trajectory_valid"].map(_truthy)
    )
    return df.loc[mask].copy()


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok"}
    return bool(value)


def _scalar_or_array(value):
    arr = np.asarray(value)
    if arr.ndim == 0:
        return float(arr)
    return value
