# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 10:48:46 2025

@author: 李
"""

import sunpy.map
import matplotlib.pyplot as plt
from astropy.io import fits
from datetime import datetime

def convert_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except ValueError:
        return date_str  # 如果转换失败，则返回原始字符串，避免崩溃

if __name__ == "__main__":
    file_path = '<DATA_ROOT>/HXI_CLEAN/hxi_imgcube_04e09t_20240808_192000_HXI_CLEAN.fits'
    hdul=fits.open(file_path)
    
    for i in range(1):#i=14,18,22
        header = hdul[i].header
        print(header)
        header['CUNIT1'] = 'arcsec'
        header['CUNIT2'] = 'arcsec'
        if 'WAVELNTH' in header:
            del header['WAVELNTH']
        if 'DATE_OBS' in header:
            header['DATE_OBS'] = convert_date(header['DATE_OBS'])
    
        if 'DATE-OBS' in header:
            header['DATE-OBS'] = convert_date(header['DATE-OBS'])
        hximap = sunpy.map.Map(hdul[i].data,header)
        hximap.plot()
        plt.text(10,80,header['ENERGY_H'],color="white")
        plt.show()