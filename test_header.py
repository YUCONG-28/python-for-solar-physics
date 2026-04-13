# -*- coding: utf-8 -*-
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

file_path0 = r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\149MHz_DeclinationDegree.fits"
file_path1 = r"<PROJECT_ROOT>\2025\20250124\RS_0447-0450\149MHz\149MHz_RightAscensionDegree.fits"
# 读取FITS文件
hdul0 = fits.open(file_path0)
header0 = hdul0[1].header
hdul1 = fits.open(file_path1)
header1 = hdul1[0].header
print(header1)
print("***********************")
# print(header1)
