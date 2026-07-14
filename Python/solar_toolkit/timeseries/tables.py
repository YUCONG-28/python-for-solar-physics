"""Tabular time-series normalization and selection.

English: Standardize pandas time columns and select an inclusive time range.

中文：规范 pandas 时间列，并按闭区间筛选时间序列。
"""

from __future__ import annotations

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


__all__ = ["crop_time_range", "normalize_time_column"]
