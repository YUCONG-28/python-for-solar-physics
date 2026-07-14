"""Soft X-ray time-series loading.

English: Load GOES/SXR tables or NetCDF products and optionally crop the
requested time interval.

中文：加载 GOES/SXR 表格或 NetCDF 产品，并可按指定时间区间裁剪。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from solar_toolkit.timeseries import crop_time_range, normalize_time_column


def load_sxr_data(
    file_path: str | Path,
    start_time=None,
    end_time=None,
    *,
    time_column: str = "time",
) -> Any:
    """Load a GOES/SXR table or NetCDF product and optionally crop by time.

    CSV and text files return a normalized :class:`pandas.DataFrame`. NetCDF
    files return an in-memory :class:`xarray.Dataset`; loading into memory
    ensures the source file can be closed before this function returns.
    """

    path = Path(file_path)
    if path.suffix.casefold() in {".cdf", ".nc", ".nc4", ".netcdf"}:
        return load_goes_sxr_dataset(path, start_time, end_time)
    if path.suffix.casefold() in {".csv", ".txt"}:
        frame = pd.read_csv(path)
    else:
        frame = pd.read_table(path)
    normalized = normalize_time_column(frame, source_column=time_column)
    if start_time is None or end_time is None:
        return normalized
    return crop_time_range(normalized, start_time, end_time)


def load_goes_sxr_dataset(
    file_path: str | Path,
    start_time=None,
    end_time=None,
    *,
    require_data: bool = False,
):
    """Load and detach a GOES SXR NetCDF dataset from its source file."""

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SXR data file does not exist: {path}")

    try:
        import xarray as xr
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "Reading GOES NetCDF data requires the optional 'xarray' dependency"
        ) from exc

    try:
        with xr.open_dataset(path) as source:
            dataset = xr.decode_cf(source)
            if start_time is not None or end_time is not None:
                start = start_time if start_time is not None else dataset.time.min()
                end = end_time if end_time is not None else dataset.time.max()
                dataset = dataset.sel(time=slice(start, end))
            dataset = dataset.load()
    except Exception as exc:
        raise RuntimeError(f"Failed to read SXR data from {path}: {exc}") from exc

    if require_data and dataset.sizes.get("time", 0) == 0:
        raise ValueError(
            f"No SXR samples found between {start_time!r} and {end_time!r}"
        )
    return dataset


__all__ = ["load_goes_sxr_dataset", "load_sxr_data"]
