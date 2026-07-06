"""Gaussian source-mask helpers.

English: Public facade for source-mask construction and connected-component
selection used by radio Gaussian fitting.

中文：射电高斯拟合中用于源区 mask 构造和连通区域选择的门面模块。
"""

from __future__ import annotations

from .gaussian import _select_peak_connected_mask, create_source_mask

__all__ = ["_select_peak_connected_mask", "create_source_mask"]
