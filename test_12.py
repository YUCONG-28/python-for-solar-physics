# -*- coding: utf-8 -*-
"""
Created on Thu May  8 09:11:53 2025

@author: 李
"""

import matplotlib.pyplot as plt

from astropy.io import fits
from datetime import datetime,timedelta

if __name__ == "__main__":
    file_path = '<DATA_ROOT>/LC/the first/23_00-23_30/ospex_results_19_apr_2025.fits'
    hdul=fits.open(file_path)
    
    primary_hdu = hdul[0]
# 查看主 HDU 的头信息
    print(primary_hdu.header)
# 访问第一个二进制表格 HDU
    table_hdu = hdul[1]
# 获取表格数据
    table_data = table_hdu.data
    print(table_data)
