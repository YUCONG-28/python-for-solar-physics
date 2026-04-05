# -*- coding: utf-8 -*-
"""
Created on Mon Mar 17 11:44:55 2025

@author: 李
"""

import os
import sunpy.map
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt

from datetime import datetime
from astropy.io import fits
from astropy.coordinates import SkyCoord

def convert_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except ValueError:
        return date_str  # 如果转换失败，则返回原始字符串，避免崩溃

if __name__ == "__main__":
    file_path = 'D:/hxidata/HXI_CLEAN/25_5_8/19_22-19_23___30-50.fits'
    hdul=fits.open(file_path)
    
    output_dir = 'D:/hxidata/HXI_CLEAN/25_5_8/plot'
    os.makedirs(output_dir, exist_ok=True)
    
    # for j in range(4):
    #     i = j*2
    header = hdul[1].header
    print(header)
    header['CUNIT1'] = 'arcsec'
    header['CUNIT2'] = 'arcsec'
    if 'WAVELNTH' in header:
        del header['WAVELNTH']
    if 'DATE_OBS' in header:
        header['DATE_OBS'] = convert_date(header['DATE_OBS'])

    if 'DATE-OBS' in header:
        header['DATE-OBS'] = convert_date(header['DATE-OBS'])
    header['crpix1']=0+header['crpix1']
    header['crpix2']=0+header['crpix2']
    hximap = sunpy.map.Map(hdul[1].data,header)
    
    #AIA_171_IMAGE='D:/Flare/JSOCdata/AIA_1600/aia.lev1_uv_24s.2024-08-08T192216Z.1600.image_lev1.fits'
    AIA_171_IMAGE='D:/Flare/JSOCdata/AIA_304/aia.lev1_euv_12s.2024-08-08T192243Z.304.image_lev1.fits'
    aia = sunpy.map.Map(AIA_171_IMAGE)
    
    bottom_left = SkyCoord(180* u.arcsec, -340* u.arcsec, frame=aia.coordinate_frame)
    top_right = SkyCoord(520* u.arcsec, 20* u.arcsec, frame=aia.coordinate_frame)

    sub_aia = aia.submap(bottom_left, top_right=top_right)
    
    fig = plt.figure(figsize=(8, 8))

    ax = fig.add_subplot(projection=sub_aia)
    sub_aia.plot(axes=ax, clip_interval=(1, 99)*u.percent)
    sub_aia.draw_grid(axes=ax)
    
    levels = [ 100, 150, 300, 500, 1000] * u.Gau
    levels =np.array([0.1,0.5,0.9])*hximap.data.max()
    bounds = ax.axis()
    cset = hximap.draw_contours(levels, axes=ax,colors=["red","blue","yellow"])
    plt.text(10,500,header['ENERGY_L'],color="white",fontsize=16)
    plt.text(60,500,"-",color="white",fontsize=16)
    plt.text(70,500,header['ENERGY_H'],color="white",fontsize=16)
    
    date_obs = sub_aia.meta.get('DATE-OBS', 'unknown_date')
    clean_date_obs = date_obs.replace(':', '-').replace('.', '-')
    
    # base_name = os.path.splitext(os.path.basename(AIA_171_IMAGE))[0]
    # output_path = os.path.join(output_dir, clean_date_obs + '.png')
    # plt.savefig(output_path, dpi=200, bbox_inches='tight')
    
    plt.show()    