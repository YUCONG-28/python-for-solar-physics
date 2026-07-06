"""X-ray, HXI, Neupert, and DEM workflow helpers.

English: First reusable helpers for loading SXR-style time-series tables,
smoothing flux arrays, and calculating finite-difference derivatives. Existing
research scripts remain runnable under ``scripts/xray_dem``.

中文: X 射线、HXI、Neupert 效应和 DEM 工作流的第一批可复用工具, 包含 SXR
时间序列表读取、通量平滑和有限差分导数计算。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from solar_toolkit.timeseries import (
    crop_time_range,
    derivative_series,
    normalize_time_column,
    smooth_series,
)


def load_sxr_data(
    file_path: str | Path,
    start_time=None,
    end_time=None,
    *,
    time_column: str = "time",
) -> pd.DataFrame:
    """Load a GOES/SXR-style CSV table and optionally crop by time."""

    path = Path(file_path)
    if path.suffix.casefold() in {".csv", ".txt"}:
        frame = pd.read_csv(path)
    else:
        frame = pd.read_table(path)
    normalized = normalize_time_column(frame, source_column=time_column)
    if start_time is None or end_time is None:
        return normalized
    return crop_time_range(normalized, start_time, end_time)


def smooth_flux_data(flux_data, window_length: int = 5, polyorder: int | None = None):
    """Smooth flux data using the shared moving-average baseline.

    ``polyorder`` is accepted for compatibility with older Neupert scripts.
    """

    _ = polyorder
    return smooth_series(flux_data, window_length=window_length)


def calculate_derivative(
    time_data_or_flux, flux_data=None, *, spacing_seconds: float | None = None
):
    """Calculate a derivative for flux data.

    If only one argument is supplied, unit spacing is used. If a time axis and a
    flux series are supplied, the median time spacing in seconds is used.
    """

    if flux_data is None:
        return derivative_series(
            time_data_or_flux, spacing_seconds=spacing_seconds or 1.0
        )
    times = pd.to_datetime(time_data_or_flux, utc=True).view("int64") / 1_000_000_000
    if len(times) > 1:
        spacing = float(pd.Series(times).diff().dropna().median())
    else:
        spacing = 1.0
    return derivative_series(flux_data, spacing_seconds=spacing_seconds or spacing)


__all__ = [
    "calculate_derivative",
    "load_sxr_data",
    "smooth_flux_data",
]
