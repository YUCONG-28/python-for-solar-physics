"""Modeling helper namespace.

English: Shared modeling boundary for Gaussian, density-model, and future
science-model helpers that should not depend on script entrypoints.

中文：高斯模型、密度模型以及后续科学模型辅助逻辑的共享边界，避免公共模型
代码依赖脚本入口。
"""

from __future__ import annotations

from solar_toolkit import gaussian
from solar_toolkit.radio import gaussian_models, newkirk

__all__ = ["gaussian", "gaussian_models", "newkirk"]
