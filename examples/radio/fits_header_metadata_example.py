# -*- coding: utf-8 -*-
# 模块用途: 测试 FITS 头信息解析和 SunPy map 元数据处理。
# 主要输入: FITS 测试文件或头信息样例。
# 主要输出/运行说明: 输出头信息检查结果，辅助定位元数据问题。
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus
"""

import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from matplotlib.colors import LogNorm
from matplotlib.patches import Circle

from solar_toolkit.path_config import load_script_config

PATH_CONFIG = load_script_config(
    "test_fits_header_metadata",
    {
        "file_path0": (
            r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450"
            r"\149MHz\149MHz_DeclinationDegree.fits"
        ),
        "file_path1": (
            r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450"
            r"\149MHz\149MHz_RightAscensionDegree.fits"
        ),
    },
)
file_path0 = PATH_CONFIG["file_path0"]
file_path1 = PATH_CONFIG["file_path1"]
# 读取FITS文件
hdul0 = fits.open(file_path0)
header0 = hdul0[0].header
hdul1 = fits.open(file_path1)
header1 = hdul1[0].header
print(header0)
print("***********************")
print(header1)
