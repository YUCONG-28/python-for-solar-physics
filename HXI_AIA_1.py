# -*- coding: utf-8 -*-
"""
Created on Thu Mar 20 14:30:50 2025

@author: 李
"""

import sunpy.map
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt

from astropy.io import fits
from datetime import datetime
from reproject import reproject_interp
from astropy.coordinates import SkyCoord
from scipy.interpolate import RegularGridInterpolator

def convert_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except ValueError:
        return date_str  # 如果转换失败，则返回原始字符串，避免崩溃

if __name__ == "__main__":
    file_path = 'D:/hxidata/HXI_CLEAN/hxi_imgcube_02e01t_20240808_192200_HXI_CLEAN.fits'
    hdul=fits.open(file_path)
    
    header = hdul[1].header
    header['CUNIT1'] = 'arcsec'
    header['CUNIT2'] = 'arcsec'
    if 'WAVELNTH' in header:
        del header['WAVELNTH']
    if 'DATE_OBS' in header:
        header['DATE_OBS'] = convert_date(header['DATE_OBS'])

    if 'DATE-OBS' in header:
        header['DATE-OBS'] = convert_date(header['DATE-OBS'])
    hximap = sunpy.map.Map(hdul[1].data,header)
    
    AIA_171_IMAGE='D:/Flare/JSOCdata/AIA_1600/aia.lev1_uv_24s.2024-08-08T192216Z.1600.image_lev1.fits'
    aia = sunpy.map.Map(AIA_171_IMAGE)
    
    bottom_left = SkyCoord(300* u.arcsec, -290* u.arcsec, frame=aia.coordinate_frame)
    top_right = SkyCoord(500* u.arcsec, -90* u.arcsec, frame=aia.coordinate_frame)

    sub_aia = aia.submap(bottom_left, top_right=top_right)
    
    
        # 2. 重投影 hximap 到 aia_smap 的坐标系
    hximap_reprojected = hximap.reproject_to(sub_aia.wcs)
    
    hximap_new_meta = sub_aia.meta.copy()
    
    # 2. 保留 hximap 的原始数据
    hximap_new = sunpy.map.Map(hximap_reprojected.data, hximap_new_meta)
    
    x = np.arange(hximap.data.shape[1])
    y = np.arange(hximap.data.shape[0])
    interp_func = RegularGridInterpolator((y, x), hximap.data, method='linear')  # method='linear' 
    x_new = np.linspace(0, hximap.data.shape[1] - 1, hximap_new.data.shape[1])
    y_new = np.linspace(0, hximap.data.shape[0] - 1, hximap_new.data.shape[0])
    X_new, Y_new = np.meshgrid(x_new, y_new, indexing='ij')
    hximap_interpolated_data = interp_func((Y_new, X_new))
    hximap_new = sunpy.map.Map(hximap_interpolated_data, hximap_new.meta)
    fig = plt.figure(figsize=(8, 8))

    ax = fig.add_subplot(projection=sub_aia)
    sub_aia.plot(axes=ax, clip_interval=(1, 99.99)*u.percent)
    sub_aia.draw_grid(axes=ax)
    
    levels =np.array([0.1,0.5])*hximap_new.data.max()*u.DN
    bounds = ax.axis()
    cset = hximap_new.draw_contours(levels, axes=ax,colors="red")

    plt.show()