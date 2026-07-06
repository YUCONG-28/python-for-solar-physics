"""Time-series helpers for solar light curves.

English: Pandas/Numpy utilities for standardizing time columns, time clipping,
smoothing, and finite-difference derivatives.

中文: 太阳光变曲线的表格时间列规范化、时间裁剪、平滑和导数计算工具。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalize_time_column(
    frame: pd.DataFrame,
    *,
    source_column: str = "time",
    target_column: str = "obs_time",
) -> pd.DataFrame:
    """Return a copy with ``target_column`` as timezone-naive UTC timestamps."""

    result = frame.copy()
    times = pd.to_datetime(result[source_column], utc=True, errors="raise")
    result[target_column] = times.dt.tz_convert(None)
    return result


def crop_time_range(
    frame: pd.DataFrame,
    start_time,
    end_time,
    *,
    time_column: str = "obs_time",
) -> pd.DataFrame:
    """Return rows inside an inclusive time range."""

    start = pd.to_datetime(start_time, utc=True).tz_convert(None)
    end = pd.to_datetime(end_time, utc=True).tz_convert(None)
    times = pd.to_datetime(frame[time_column], utc=True).dt.tz_convert(None)
    return frame.loc[(times >= start) & (times <= end)].copy()


def smooth_series(values, *, window_length: int = 5) -> np.ndarray:
    """Smooth values with a centered moving average and zero-padded edges."""

    window = max(1, int(window_length))
    if window % 2 == 0:
        window += 1
    array = np.asarray(values, dtype=float)
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(array, kernel, mode="same")


def derivative_series(values, *, spacing_seconds: float = 1.0) -> np.ndarray:
    """Return a shape-stable finite-difference derivative."""

    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return np.asarray([], dtype=float)
    if array.size == 1:
        return np.zeros_like(array, dtype=float)
    return np.gradient(array, float(spacing_seconds))


__all__ = [
    "crop_time_range",
    "derivative_series",
    "normalize_time_column",
    "smooth_series",
]
