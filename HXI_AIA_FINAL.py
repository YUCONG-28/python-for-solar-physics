# -*- coding: utf-8 -*-
"""
Created on Thu Apr 24 22:20:25 2025

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

    vmin = 1  # 最小值（对数尺度）
    
    input_dir_AIA = 'D:/Flare/JSOCdata/AIA_131/fits/44/'
    output_dir = 'D:/hxidata/HXI_CLEAN/25_4_24/plot/20-50/131/'
    os.makedirs(output_dir, exist_ok=True)
    
    AIA_file_paths = [os.path.join(input_dir_AIA, f) for f in os.listdir(input_dir_AIA) if f.endswith('.fits')]
    aia_sequence = sunpy.map.Map(AIA_file_paths, sequence=True)
    
    aia_my_map = sunpy.map.Map(aia_sequence[1])

    hxi_file_path = 'D:/hxidata/HXI_CLEAN/25_4_24/20-50.fits'
    hdul = fits.open(hxi_file_path)

    # 确保 i 不会超过 hdul 的长度
    for i in range(0, min(len(aia_sequence), len(hdul))):
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
        header['crpix1'] = 9 + header['crpix1']  # 右
        header['crpix2'] = 1 + header['crpix2']  # 上
        hximap = sunpy.map.Map(hdul[i].data, header)

        # 确保 i + j 不会超过 aia_sequence 的长度
        for j in range(4):
            if i + j < len(aia_sequence):
                AIA_1600_IMAGE = aia_sequence[4*i + j]
                my_map = sunpy.map.Map(AIA_1600_IMAGE)
                roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
                roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
                my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
                    
                fig = plt.figure(figsize=(8, 8))
                
                ax = fig.add_subplot(projection=my_submap)
                my_submap.plot(axes=ax, norm=colors.LogNorm(vmin=vmin, vmax=0.1*np.max(my_submap.data)))
                my_submap.draw_grid(axes=ax)
                
                levels = np.array([0.1, 0.5, 0.9]) * hximap.data.max()
                levels = np.sort(levels)
                for k in range(1, len(levels)):
                    if levels[k] <= levels[k-1]:
                        levels[k] = levels[k-1] + 1e-9  # Add a small value
                
                bounds = ax.axis()
                cset = hximap.draw_contours(levels, axes=ax, colors=["black", "purple", "yellow"])
                plt.text(10, 300, header['ENERGY_H'], color="white", fontsize=16)
                
                path = AIA_file_paths[4*i + j]
                base_name = os.path.splitext(os.path.basename(path))[0]
                output_path = os.path.join(output_dir, base_name + '.png')
                plt.savefig(output_path, dpi=200, bbox_inches='tight')
                
                plt.show()