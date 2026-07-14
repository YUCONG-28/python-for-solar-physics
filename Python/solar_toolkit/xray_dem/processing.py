"""Soft X-ray and Neupert-effect numerical helpers.

English: Smooth flux arrays and calculate finite-difference derivatives with
explicit numerical modes. The default modes preserve the lightweight public
API, while the Savitzky-Golay and forward-difference modes reproduce the
historical GOES/Neupert scripts.

中文：使用显式数值模式平滑软 X 射线通量并计算有限差分导数。默认模式保持
轻量公共 API 的既有行为；Savitzky-Golay 与前向差分模式用于复现历史 GOES/
Neupert 脚本。
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from solar_toolkit.timeseries import derivative_series, smooth_series

SmoothingMethod = Literal["moving-average", "savgol"]
DerivativeMethod = Literal["median-gradient", "gradient", "forward"]


def smooth_flux_data(
    flux_data,
    window_length: int = 5,
    polyorder: int | None = None,
    *,
    method: SmoothingMethod = "moving-average",
    adjust_even_window: bool = False,
    clamp_to_data: bool = False,
) -> np.ndarray:
    """Return a smoothed flux array.

    Parameters
    ----------
    method
        ``"moving-average"`` keeps the original public-package behavior.
        ``"savgol"`` uses :func:`scipy.signal.savgol_filter`, matching the
        historical GOES analysis scripts.
    adjust_even_window
        Increase an even Savitzky-Golay window by one. This opt-in behavior
        reproduces the dedicated Neupert comparison script without changing
        the other scripts, which historically passed an even window directly.
    clamp_to_data
        Limit the window and polynomial order to the available samples. This
        reproduces the historical defensive Neupert helper.
    """

    if method == "moving-average":
        return smooth_series(flux_data, window_length=window_length)
    if method != "savgol":
        raise ValueError(f"Unsupported smoothing method: {method!r}")

    array = np.asarray(flux_data, dtype=float)
    window = int(window_length)
    order = 3 if polyorder is None else int(polyorder)
    if window < 1:
        raise ValueError("window_length must be positive")
    if order < 0:
        raise ValueError("polyorder must be non-negative")

    if adjust_even_window and window % 2 == 0:
        window += 1

    if clamp_to_data:
        maximum = array.size if array.size % 2 == 1 else array.size - 1
        if maximum < 1:
            raise ValueError("At least one flux sample is required")
        window = min(window, maximum)
        order = min(order, window - 1)

    if order >= window:
        raise ValueError("polyorder must be less than window_length")

    from scipy.signal import savgol_filter

    return np.asarray(savgol_filter(array, window, order), dtype=float)


def _time_seconds(time_data) -> np.ndarray:
    values = np.asarray(getattr(time_data, "values", time_data))
    if np.issubdtype(values.dtype, np.datetime64):
        return values.astype("datetime64[ns]").astype(np.int64) / 1_000_000_000
    converted = pd.to_datetime(values, utc=True)
    nanoseconds = converted.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    return nanoseconds / 1_000_000_000


def calculate_derivative(
    time_data_or_flux,
    flux_data=None,
    *,
    spacing_seconds: float | None = None,
    method: DerivativeMethod = "median-gradient",
) -> np.ndarray:
    """Calculate a derivative for flux data.

    If only one argument is supplied, unit spacing is used. With a time axis,
    ``"median-gradient"`` preserves the original public-package behavior,
    ``"gradient"`` evaluates :func:`numpy.gradient` at exact sample times,
    and ``"forward"`` returns the historical ``diff(flux) / diff(time)`` result.
    """

    if flux_data is None:
        if method == "forward":
            values = np.asarray(time_data_or_flux, dtype=float)
            spacing = 1.0 if spacing_seconds is None else float(spacing_seconds)
            return np.diff(values) / spacing
        if method not in {"median-gradient", "gradient"}:
            raise ValueError(f"Unsupported derivative method: {method!r}")
        return derivative_series(
            time_data_or_flux,
            spacing_seconds=1.0 if spacing_seconds is None else spacing_seconds,
        )

    values = np.asarray(flux_data, dtype=float)
    times = _time_seconds(time_data_or_flux)
    if values.size != times.size:
        raise ValueError("time_data and flux_data must have the same length")
    if values.size < 2:
        if method == "forward":
            return np.asarray([], dtype=float)
        return np.zeros_like(values, dtype=float)

    if spacing_seconds is not None:
        if method == "forward":
            return np.diff(values) / float(spacing_seconds)
        if method in {"median-gradient", "gradient"}:
            return np.gradient(values, float(spacing_seconds))
        raise ValueError(f"Unsupported derivative method: {method!r}")

    if method == "forward":
        return np.diff(values) / np.diff(times)
    if method == "gradient":
        return np.gradient(values, times)
    if method != "median-gradient":
        raise ValueError(f"Unsupported derivative method: {method!r}")

    spacing = float(np.median(np.diff(times)))
    return derivative_series(values, spacing_seconds=spacing)


__all__ = [
    "DerivativeMethod",
    "SmoothingMethod",
    "calculate_derivative",
    "smooth_flux_data",
]
