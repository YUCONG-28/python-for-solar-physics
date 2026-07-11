"""Time-series helpers for solar light curves.

English: Pandas/Numpy utilities for standardizing time columns, time clipping,
smoothing, and finite-difference derivatives.

中文：太阳光变曲线的时间列规范化、时间裁剪、平滑和有限差分导数工具。
"""

from .processing import derivative_series, smooth_series
from .tables import crop_time_range, normalize_time_column

__all__ = [
    "crop_time_range",
    "derivative_series",
    "normalize_time_column",
    "smooth_series",
]
