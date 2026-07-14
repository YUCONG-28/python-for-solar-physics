"""Gaussian fitting I/O helpers.

English: Public facade for saving radio Gaussian diagnostics and per-band
configuration lookup.

中文：保存射电高斯拟合诊断结果和查询分频段配置的门面模块。
"""

from __future__ import annotations

from .gaussian import save_gaussian_diagnostics_row

__all__ = ["save_gaussian_diagnostics_row"]
