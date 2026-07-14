"""Gaussian fitting diagnostics.

English: Public facade for Gaussian fit quality checks and diagnostic row
construction.

中文：高斯拟合质量检查和诊断行生成相关函数门面模块。
"""

from __future__ import annotations

from .gaussian import (
    _attach_gaussian_fit_metadata,
    _fit_failure_warning,
    _gaussian_quality_config,
    _gaussian_result_diagnostics_row,
    _set_gaussian_failure_diag,
    _update_gaussian_quality,
    multi_gaussian_diagnostics_rows,
)

__all__ = [
    "_attach_gaussian_fit_metadata",
    "_fit_failure_warning",
    "_gaussian_quality_config",
    "_gaussian_result_diagnostics_row",
    "_set_gaussian_failure_diag",
    "_update_gaussian_quality",
    "multi_gaussian_diagnostics_rows",
]
