# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025

@author: Severus
"""

from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from astropy.wcs import WCS
from matplotlib.colors import LogNorm

file_path0 = r'<PROJECT_ROOT>\2025\20250124\DEM\aia_data\aia.lev1_euv_12s.2025-01-24T044747Z.211.image_lev1.fits'
file_path1 = r'<PROJECT_ROOT>\2025\20250124\share\Data\UnPack\20250124UT0447-0450\ImageData_RRLL\149MHz\RR\149MHz_2025124_043739_681.fits'
# 读取FITS文件
hdul0 = fits.open(file_path0)
header0 = hdul0[1].header
hdul1 = fits.open(file_path1)
header1 = hdul1[0].header
print(header1)
print('***********************')
# print(header1)
