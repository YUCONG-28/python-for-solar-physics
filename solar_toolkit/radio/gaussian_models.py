"""Gaussian source models.

English: Public facade for analytic Gaussian model functions used by radio
source fitting.

中文：射电源拟合中使用的解析高斯模型函数门面模块。
"""

from __future__ import annotations

from .gaussian import (
    elliptical_gaussian_2d,
    elliptical_gaussian_2d_with_constant_bg,
    elliptical_gaussian_2d_with_plane_bg,
    gaussian_only_from_popt,
)

__all__ = [
    "elliptical_gaussian_2d",
    "elliptical_gaussian_2d_with_constant_bg",
    "elliptical_gaussian_2d_with_plane_bg",
    "gaussian_only_from_popt",
]
