"""Numerical CME image processing.

English: Provide array-level CME products without plotting or workflow side
effects.

中文：提供不包含绘图或工作流副作用的 CME 数组级处理结果。
"""

from __future__ import annotations

import numpy as np


def running_difference(current, previous) -> np.ndarray:
    """Return ``current - previous`` as a float/array preserving NumPy rules."""

    return np.asarray(current) - np.asarray(previous)


__all__ = ["running_difference"]
