"""Gaussian fitting background and noise estimation helpers.

English: Public facade for background/noise utilities used before fitting
radio source Gaussians.

中文：射电源高斯拟合前使用的背景与噪声估计辅助函数门面模块。
"""

from __future__ import annotations

from .gaussian import _safe_rms_map, estimate_background_noise

__all__ = ["_safe_rms_map", "estimate_background_noise"]
