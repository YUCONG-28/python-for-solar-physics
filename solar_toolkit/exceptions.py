"""Warning classes exposed by :mod:`solar_toolkit`.

English: Public warning categories let applications filter toolkit warnings
without suppressing unrelated warnings from Astropy, SunPy, or NumPy.

中文：公共警告类别允许应用程序只筛选本工具包的警告，而不会屏蔽
Astropy、SunPy 或 NumPy 的其他警告。
"""

from __future__ import annotations


class SolarToolkitDeprecationWarning(Warning):
    """Warning category for deprecated solar-toolkit APIs."""


__all__ = ["SolarToolkitDeprecationWarning"]
