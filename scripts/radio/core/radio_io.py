"""Neutral I/O, parsing, and diagnostic helpers for radio workflows."""

from __future__ import annotations

import csv
import datetime
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

BoolArray = NDArray[np.bool_]
FloatArray = NDArray[np.float64]
IntArray = NDArray[np.intp]

GAUSSIAN_DIAGNOSTIC_FIELDS = [
    "source_file",
    "time",
    "freq",
    "polarization",
    "reason",
    "finite_pixel_count",
    "center_x_arcsec",
    "center_y_arcsec",
    "center_x_pixel",
    "center_y_pixel",
    "raw_peak_x_arcsec",
    "raw_peak_y_arcsec",
    "raw_peak_x_pixel",
    "raw_peak_y_pixel",
    "center_peak_dx_arcsec",
    "center_peak_dy_arcsec",
    "center_peak_distance_arcsec",
    "sigma_x_pixel",
    "sigma_y_pixel",
    "fwhm_x_pixel",
    "fwhm_y_pixel",
    "fwhm_width_arcsec",
    "fwhm_height_arcsec",
    "fwhm_major_arcsec",
    "fwhm_minor_arcsec",
    "max_fwhm_arcsec",
    "fwhm_valid",
    "overlay_valid",
    "trajectory_valid",
    "coordinate_roundtrip_error_pixel",
    "theta_rad",
    "amplitude",
    "background_level",
    "noise_sigma",
    "snr",
    "residual_rms",
    "mask_pixel_count",
    "quality_flag",
    "quality_flag_detail",
    "background_strategy",
    "background_use_for_mask",
    "background_use_for_display",
    "background_use_for_fit",
    "display_input_type",
    "background_mesh_size",
    "background_rms_median",
    "background_level_median",
    "source_snr_peak",
    "source_snr_mean",
    "mask_method",
    "fit_peak_fraction_threshold_used",
    "fit_peak_fraction_candidate_counts",
    "background_enabled",
    "background_mode_requested",
    "background_mode_used",
    "background_scale",
    "use_background_subtracted_for_gaussian_fit",
    "fit_used_background_subtracted",
    "fit_input_type",
    "fit_background_model",
    "gaussian_fit_method",
    "roi_used",
    "roi_shape",
    "fit_pixel_count_before_limit",
    "fit_pixel_count_after_limit",
    "maxfev",
    "initial_center_pixel",
    "initial_sigma_x_pixel",
    "initial_sigma_y_pixel",
    "normalization_scale",
    "peak",
    "threshold",
]

DRIFT_RATE_DIAGNOSTIC_FIELDS = [
    "source_file",
    "label",
    "mode",
    "t_start",
    "t_end",
    "f_start_mhz",
    "f_end_mhz",
    "duration_s",
    "bandwidth_mhz",
    "drift_rate_mhz_s",
    "abs_drift_rate_mhz_s",
    "color",
    "quality_flag",
    "warning",
]


def normalize_path(path: str | os.PathLike | None, base_dir: str | os.PathLike | None = None) -> str | None:
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute() and base_dir:
        candidate = Path(base_dir) / candidate
    return str(candidate.expanduser())


def ensure_output_dir(path: str | os.PathLike) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def read_json_file(path: str | os.PathLike, default: Any = None) -> Any:
    candidate = Path(path)
    if not candidate.exists():
        return default
    with candidate.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json_file(path: str | os.PathLike, payload: Any) -> Path:
    candidate = Path(path)
    ensure_output_dir(candidate.parent or ".")
    with candidate.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return candidate


def read_csv_dataframe(path: str | os.PathLike, default: pd.DataFrame | None = None) -> pd.DataFrame:
    candidate = Path(path)
    if not candidate.exists():
        return pd.DataFrame() if default is None else default.copy()
    return pd.read_csv(candidate)


def write_csv_rows(path: str | os.PathLike, rows: list[dict], fieldnames: list[str]) -> Path:
    candidate = Path(path)
    ensure_output_dir(candidate.parent or ".")
    with candidate.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return candidate


def safe_series(df: pd.DataFrame, column: str, default=np.nan) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def log_skipped_row(prefix: str, index, reason: str) -> str:
    message = f"{prefix} skipped row {index}: {reason}"
    print(message)
    return message


def summarize_invalid_reasons(df: pd.DataFrame, valid_column: str, reason_column: str) -> dict[str, int]:
    if df.empty or valid_column not in df.columns or reason_column not in df.columns:
        return {}
    invalid = df[~df[valid_column].map(truthy)]
    if invalid.empty:
        return {}
    counts = invalid[reason_column].fillna("unknown").astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def parse_datetime_value(value) -> datetime.datetime | None:
    """Parse config/header datetime values robustly."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    text = str(value).strip()
    if not text or text.lower() == "none" or text == "Unknown":
        return None
    text = text.replace("Z", "").replace("T", " ")
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H%M%S.%f",
        "%Y-%m-%d %H%M%S",
        "%Y%m%d %H%M%S.%f",
        "%Y%m%d %H%M%S",
        "%Y%m%dT%H%M%S.%f",
        "%Y%m%dT%H%M%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def index_range_from_values(
    arr: np.ndarray, lo: float, hi: float, allow_full_fallback: bool = True
) -> tuple[int, int] | None:
    arr = np.asarray(arr)
    if lo > hi:
        lo, hi = hi, lo
    mask = np.isfinite(arr) & (arr >= lo) & (arr <= hi)
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        if allow_full_fallback:
            return 0, len(arr) - 1
        return None
    return int(idx[0]), int(idx[-1])


def index_range_from_time_values(arr: np.ndarray, lo: float, hi: float) -> tuple[int, int] | None:
    return index_range_from_values(arr, lo, hi, allow_full_fallback=False)


def spectrogram_panel_enabled(cfg: dict) -> bool:
    return bool(cfg.get("enable_spectrogram_panel", False))


def background_enabled_for_display(cfg: dict) -> bool:
    return resolve_background_workflow(cfg) in {"display_only", "display_and_fit"}


def background_enabled_for_fit(cfg: dict) -> bool:
    return resolve_background_workflow(cfg) in {"fit_only", "display_and_fit"}


def resolve_background_workflow(cfg: dict) -> str:
    workflow = str(cfg.get("radio_background_workflow", "off") or "off").lower()
    if workflow in {"off", "display_only", "fit_only", "display_and_fit"}:
        return workflow
    display = bool(cfg.get("background_use_for_display", False))
    fit = bool(cfg.get("background_use_for_fit", False))
    if display and fit:
        return "display_and_fit"
    if display:
        return "display_only"
    if fit:
        return "fit_only"
    return "off"


def plot_output_subdir(cfg: dict) -> str:
    use_gaussian = cfg.get("enable_gaussian_overlay", False)
    use_spec = spectrogram_panel_enabled(cfg)
    show_bgsub = background_enabled_for_display(cfg)
    bgfit = background_enabled_for_fit(cfg) and use_gaussian and not show_bgsub
    if show_bgsub:
        parts = []
        if use_gaussian:
            parts.append("gaussian")
        if use_spec:
            parts.append("spectrogram")
        parts.append("background_subtracted")
        return "_".join(parts)
    if bgfit:
        return "gaussian_bgfit_overlay"
    if use_gaussian and use_spec:
        return "gaussian_spectrogram_overlay"
    if use_spec:
        return cfg.get("spectrogram_output_subdir", "radio_spectrogram_composite")
    if use_gaussian:
        return "gaussian_overlay"
    return "radio_source_maps"


def drift_output_path(cfg: dict, key: str) -> str:
    if key == "drift_rate_diagnostics_csv" and key not in cfg:
        key = "drift_diagnostics_csv"
    path = str(cfg.get(key, "") or "")
    if not path:
        path = str(key)
    if os.path.isabs(path):
        return path
    if key == "drift_rate_selection_json":
        return os.path.abspath(path)
    output_dir = cfg.get("output_dir") or os.getcwd()
    return os.path.join(output_dir, plot_output_subdir(cfg), path)


def truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "ok"}
    return bool(value)

