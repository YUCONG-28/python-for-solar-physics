# -*- coding: utf-8 -*-
"""
Created on Fri Apr 18 22:13:45 2025

@author: 李
"""

import os
import sunpy.map

import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from datetime import datetime
from astropy.io import fits
from astropy.coordinates import SkyCoord

def convert_date(date_str):
    try:
        return datetime.strptime(date_str, "%d-%b-%y %H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    except ValueError:
        return date_str  # 如果转换失败，则返回原始字符串，避免崩溃

if __name__ == "__main__":

    vmin = 10  # 最小值（对数尺度）
    vmax = 1600  # 最大值（对数尺度）
    norm = colors.LogNorm(vmin=vmin, vmax=vmax)
    
    input_dir_AIA = '<DATA_ROOT>/JSOCdata/AIA_1600/'
    input_dir_HMI = '<DATA_ROOT>/JSOCdata/HMI/'
    output_dir = '<DATA_ROOT>/HXI_CLEAN/25_4_18'
    os.makedirs(output_dir, exist_ok=True)
    
    AIA_file_paths = [os.path.join(input_dir_AIA, f) for f in os.listdir(input_dir_AIA) if f.endswith('.fits')]
    HMI_file_paths = [os.path.join(input_dir_HMI, f) for f in os.listdir(input_dir_HMI) if f.endswith('.fits')]
    aia_sequence = sunpy.map.Map(AIA_file_paths, sequence=True)[51:71]
    hmi_sequence = sunpy.map.Map(HMI_file_paths, sequence=True)[28:38]
    hmi_index = 0
    
    aia_my_map = sunpy.map.Map(aia_sequence[1])
    roi_bottom_left_aia = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=aia_my_map.coordinate_frame)
    roi_top_right_aia = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=aia_my_map.coordinate_frame)
    aia_cutout_map = aia_my_map.submap(roi_bottom_left_aia, top_right=roi_top_right_aia)
    
    hmi_my_map = sunpy.map.Map(hmi_sequence[1])
    roi_bottom_left_hmi = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=hmi_my_map.coordinate_frame)
    roi_top_right_hmi = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=hmi_my_map.coordinate_frame)
    hmi_cutout_map = hmi_my_map.submap(roi_bottom_left_hmi, top_right=roi_top_right_hmi)
    
    sum=0
    SUM=0
    
    for i in range(0, len(aia_sequence), 2):
        for j in range(2):
            if i + j < len(aia_sequence):
                AIA_1600_IMAGE = aia_sequence[i + j]
                my_map = sunpy.map.Map(AIA_1600_IMAGE)
                roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
                roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
                my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
                #normalized_map = sunpy.map.Map(my_submap.data/my_submap.exposure_time, my_submap.meta)
    
                if hmi_index < len(hmi_sequence):
                    HMI_IMAGE = hmi_sequence[hmi_index]
                    hmi = sunpy.map.Map(HMI_IMAGE)
                    hmi = hmi.submap(roi_bottom_left, top_right=roi_top_right)
    
                    aia = my_submap.reproject_to(hmi.wcs)
                    aia.nickname = 'AIA'
    
                    segmented = aia.data > 100
                    masked_data = np.where(segmented, aia.data, 0.) 
                    aia1 = sunpy.map.Map(masked_data, aia.meta)

                    sum=sum+segmented
                    SUM = SUM + aia.data
    
        hmi_index += 1
    
    sum = sum / 20
    SUM = SUM / 20
    masked_data_pro = np.where(sum, SUM, 0.) 
    aia2 = sunpy.map.Map(masked_data_pro, aia.meta)
                    
    file_path = '<DATA_ROOT>/HXI_CLEAN/hxi_imgcube_01e01t_20240808_192000_HXI_CLEAN.fits'
    hdul=fits.open(file_path)
    header = hdul[0].header
    print(header)
    header['CUNIT1'] = 'arcsec'
    header['CUNIT2'] = 'arcsec'
    if 'WAVELNTH' in header:
        del header['WAVELNTH']
    if 'DATE_OBS' in header:
        header['DATE_OBS'] = convert_date(header['DATE_OBS'])
    
    if 'DATE-OBS' in header:
        header['DATE-OBS'] = convert_date(header['DATE-OBS'])
    header['crpix1']=9+header['crpix1']#右
    header['crpix2']=1+header['crpix2']#上
    hximap = sunpy.map.Map(hdul[0].data,header)
    
    fig = plt.figure(figsize=(8, 8))
    
    ax = fig.add_subplot(projection=aia2)
    aia2.plot(axes=ax, cmap='hmimag',norm=norm)
    aia2.draw_grid(axes=ax)
    
    levels = [100, 150, 300, 500, 1000] * u.Gau
    levels =np.array([0.1,0.5,0.9])*hximap.data.max()
    bounds = ax.axis()
    cset = hximap.draw_contours(levels, axes=ax,colors=["red","blue","yellow"])
    plt.text(10,300,header['ENERGY_H'],color="white",fontsize=16)
    
    plt.title("2024-08-08 19:21:30-19:22:00")
    
    path = AIA_file_paths[51]
    base_name = os.path.splitext(os.path.basename(path))[0]
    output_path = os.path.join(output_dir, base_name + '.png')
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    
    plt.show()