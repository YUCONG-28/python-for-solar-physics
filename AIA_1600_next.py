# -*- coding: utf-8 -*-
"""
Created on Tue Mar 25 23:34:10 2025

@author: 李
"""

import os
import glob
import sunpy.map

import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from astropy.coordinates import SkyCoord

vmin = 10  # 最小值（对数尺度）
vmax = 2000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

input_dir_AIA = '<DATA_ROOT>/JSOCdata/AIA_1600/'
input_dir_HMI = '<DATA_ROOT>/JSOCdata/HMI/'
output_dir = '<DATA_ROOT>/JSOCdata/AIA_1600/plot_pro/'
os.makedirs(output_dir, exist_ok=True)
fits_files_AIA = glob.glob(os.path.join(input_dir_AIA, "*.fits"))[51:71]

hmi_files = glob.glob(os.path.join(input_dir_HMI, "*.fits"))[28:38]
hmi_index = 0

for i in range(0, len(fits_files_AIA), 2):
    for j in range(2):
        if i + j < len(fits_files_AIA):
            AIA_1600_IMAGE = fits_files_AIA[i + j]
            my_map = sunpy.map.Map(AIA_1600_IMAGE)
            roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
            roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
            my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
            normalized_map = sunpy.map.Map(my_submap.data/my_submap.exposure_time, my_submap.meta)

            if hmi_index < len(hmi_files):
                HMI_IMAGE = hmi_files[hmi_index]
                hmi = sunpy.map.Map(HMI_IMAGE)
                hmi = hmi.submap(roi_bottom_left, top_right=roi_top_right)

                aia = normalized_map.reproject_to(hmi.wcs)
                aia.nickname = 'AIA'

                segmented = aia.data > 100
                masked_data = np.where(segmented, aia.data, 0.) 
                aia1 = sunpy.map.Map(masked_data, aia.meta)

                fig = plt.figure()
                ax = fig.add_subplot(projection=aia1)
                aia1.plot(axes=ax, cmap="hmimag", norm=norm)

                base_name = os.path.splitext(os.path.basename(AIA_1600_IMAGE))[0]
                output_path = os.path.join(output_dir, base_name + '.png')
                plt.savefig(output_path, dpi=200, bbox_inches='tight')

                # plt.show()

    hmi_index += 1
    