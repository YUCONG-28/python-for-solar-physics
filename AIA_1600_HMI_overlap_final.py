# -*- coding: utf-8 -*-
"""
Created on Thu May  8 18:56:45 2025

@author: 李
"""

import os
import sunpy.map
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
from astropy.coordinates import SkyCoord
from scipy.ndimage import gaussian_filter

input_dir_AIA = '<DATA_ROOT>/JSOCdata/AIA_1600/'
input_dir_HMI = '<DATA_ROOT>/JSOCdata/HMI/fits/'
output_dir = '<DATA_ROOT>/JSOCdata/AIA_1600_HMI_3'
os.makedirs(output_dir, exist_ok=True)

AIA_file_paths = [os.path.join(input_dir_AIA, f) for f in os.listdir(input_dir_AIA) if f.endswith('.fits')]
HMI_file_paths = [os.path.join(input_dir_HMI, f) for f in os.listdir(input_dir_HMI) if f.endswith('.fits')]
aia_sequence = sunpy.map.Map(AIA_file_paths, sequence=True)
hmi_sequence = sunpy.map.Map(HMI_file_paths, sequence=True)
hmi_index = 0

# 设置HMI数据的阈值
threshold = 49 * u.Gauss

# 设置高斯滤波的标准差，这个值越大，平滑效果越明显
sigma = 7

for i in range(0, len(aia_sequence), 2):
    for j in range(2):
        if i + j < len(aia_sequence):
            fig = plt.figure(figsize=(8, 8))
            AIA_1600_IMAGE = aia_sequence[i + j]
            my_map = sunpy.map.Map(AIA_1600_IMAGE)
            roi_bottom_left = SkyCoord(Tx=180*u.arcsec, Ty=-340*u.arcsec, frame=my_map.coordinate_frame)
            roi_top_right = SkyCoord(Tx=520*u.arcsec, Ty=20*u.arcsec, frame=my_map.coordinate_frame)
            my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)

            ax = fig.add_subplot(projection=my_submap)
            my_submap.plot(axes=ax, clip_interval=(1, 99.7)*u.percent)
            my_submap.draw_grid(axes=ax)

            levels = [100, 150, 300, 500, 1000] * u.Gauss
            levels = np.concatenate((-1 * levels[::-1], levels))
            bounds = ax.axis()

            if hmi_index < len(hmi_sequence):
                HMI_IMAGE = hmi_sequence[hmi_index]
                hmi = sunpy.map.Map(HMI_IMAGE)
                hmi = hmi.submap(roi_bottom_left, top_right=roi_top_right)

                # 应用阈值
                hmi_data = hmi.data * hmi.unit
                hmi_data[np.abs(hmi_data) < threshold] = 0 * u.Gauss

                # 进行高斯滤波平滑处理
                smoothed_data = gaussian_filter(hmi_data.value, sigma=sigma) * hmi_data.unit

                hmi = sunpy.map.Map(smoothed_data, hmi.meta)

                # 只绘制轮廓，不填充，并设置轮廓线宽度
                cset = hmi.draw_contours(levels, axes=ax, cmap='seismic', alpha=0.5, filled=False, linewidths=2)
                ax.axis(bounds)

                date_obs = hmi.meta.get('DATE-OBS', 'unknown_date')
                clean_date_obs = date_obs.replace(':', '-').replace('.', '-')
                plt.title(clean_date_obs)

                path = AIA_file_paths[i + j]
                base_name = os.path.splitext(os.path.basename(path))[0]
                output_path = os.path.join(output_dir, base_name + '.png')
                plt.savefig(output_path, dpi=200, bbox_inches='tight')

                plt.show()

    hmi_index += 1