# -*- coding: utf-8 -*-
"""
Created on Thu Apr 10 17:29:40 2025

@author: 李
"""

import os
import glob
import sunpy.map
from PIL import Image  # 用于图片处理

import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface

vmin = 10  # 最小值（对数尺度）
vmax = 2000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

input_dir_AIA = '<DATA_ROOT>/JSOCdata/AIA_1600/'
input_dir_HMI = '<DATA_ROOT>/JSOCdata/HMI/'
output_dir = '<DATA_ROOT>/JSOCdata/AIA_1600_HMI_overlap'
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

with propagate_with_solar_surface():
    aia_sequence_aligned = sunpy.map.Map([m.reproject_to(aia_cutout_map.wcs) for m in aia_sequence], sequence=True)

with propagate_with_solar_surface():
    hmi_sequence_aligned = sunpy.map.Map([m.reproject_to(hmi_cutout_map.wcs) for m in hmi_sequence], sequence=True)

sum=0
SUM=0

for i in range(0, len(aia_sequence_aligned), 2):
    for j in range(2):
        if i + j < len(aia_sequence_aligned):
            AIA_1600_IMAGE = aia_sequence_aligned[i + j]
            my_map = sunpy.map.Map(AIA_1600_IMAGE)
            roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
            roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
            my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
            #normalized_map = sunpy.map.Map(my_submap.data/my_submap.exposure_time, my_submap.meta)

            if hmi_index < len(hmi_sequence_aligned):
                HMI_IMAGE = hmi_sequence_aligned[hmi_index]
                hmi = sunpy.map.Map(HMI_IMAGE)
                hmi = hmi.submap(roi_bottom_left, top_right=roi_top_right)

                aia = my_submap.reproject_to(hmi.wcs)
                aia.nickname = 'AIA'

                segmented = aia.data > 100
                masked_data = np.where(segmented, aia.data, 0.) 
                aia1 = sunpy.map.Map(masked_data, aia.meta)

                # 从元数据中提取时间信息
                date_obs = aia1.meta.get('DATE-OBS', 'unknown_date')
                # 去除时间字符串中的特殊字符
                clean_date_obs = date_obs.replace(':', '-').replace('.', '-')
                
                fig = plt.figure()
                ax = fig.add_subplot(projection=aia1)
                plt.title = (clean_date_obs)
                aia1.plot(axes=ax, cmap="hmimag", norm=norm)

                # sum=sum+segmented
                # SUM = SUM + aia.data
                
                
                file_path = AIA_file_paths[51 + i + j]
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(output_dir, base_name + '.png')
                plt.savefig(output_path, dpi=200, bbox_inches='tight')

                plt.show()

    hmi_index += 1

# sum = sum / 20
# SUM = SUM / 20
# masked_data_pro = np.where(sum, SUM, 0.) 
# aia2 = sunpy.map.Map(masked_data_pro, aia.meta)
                
# fig_pro = plt.figure()
# ax_pro = fig_pro.add_subplot(projection=aia2)
# aia2.plot(axes=ax_pro, cmap='hmimag',norm=norm)

# file_path = AIA_file_paths[51]
# base_name = os.path.splitext(os.path.basename(file_path))[0]
# output_path = os.path.join(output_dir, base_name + '.png')
# plt.savefig(output_path, dpi=200, bbox_inches='tight')

# plt.show()