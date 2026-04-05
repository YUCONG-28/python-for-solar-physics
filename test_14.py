# -*- coding: utf-8 -*-
"""
Created on Sat May 17 00:03:19 2025

@author: 李
"""

import os
import glob
import sunpy.map
import matplotlib.pyplot as plt
import astropy.units as u
import matplotlib.colors as colors
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
import numpy as np

input_dir = 'D:/Flare/JSOCdata/AIA_94/'
output_dir = 'D:/Flare/JSOCdata/AIA_94/plot/'
os.makedirs(output_dir, exist_ok=True)
fits_files = sorted(glob.glob(os.path.join(input_dir, "*.fits")))

vmin = 1  # 最小值（对数尺度）
vmax = 2000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

# 自定义颜色映射，正为白色，负为黑色
cmap = colors.LinearSegmentedColormap.from_list('custom_cmap', [(0, 'black'), (0.5, 'gray'), (1, 'white')])

for i in range(len(fits_files) - 1):
    # 读取前一个和后一个 FITS 文件
    file_path_prev = fits_files[i]
    file_path_next = fits_files[i + 1]

    # 读取前一个和后一个地图
    my_map_prev = sunpy.map.Map(file_path_prev)
    my_map_next = sunpy.map.Map(file_path_next)

    # 定义感兴趣区域
    roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=my_map_prev.coordinate_frame)
    roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=my_map_prev.coordinate_frame)

    # 获取前一个和后一个子地图
    my_submap_prev = my_map_prev.submap(roi_bottom_left, top_right=roi_top_right)
    my_submap_next = my_map_next.submap(roi_bottom_left, top_right=roi_top_right)

    # 归一化地图
    normalized_map_prev = sunpy.map.Map(my_submap_prev.data / my_submap_prev.exposure_time, my_submap_prev.meta)
    normalized_map_next = sunpy.map.Map(my_submap_next.data / my_submap_next.exposure_time, my_submap_next.meta)

    # 进行坐标传播和重投影
    with propagate_with_solar_surface():
        aligned_map_prev = normalized_map_prev.reproject_to(my_map_prev.wcs)
        aligned_map_next = normalized_map_next.reproject_to(my_map_next.wcs)

    # 计算差值数组
    diff_data = aligned_map_prev.data - aligned_map_next.data

    # 创建差值地图
    diff_map = sunpy.map.Map(diff_data, my_submap_prev.meta)

    # 画图
    fig = plt.figure()
    ax = fig.add_subplot(projection=diff_map)
    diff_map.plot(axes=ax, cmap=cmap)
    plt.show()

    # 保存图片
    # output_filename = f"{os.path.splitext(os.path.basename(file_path_prev))[0]}_{os.path.splitext(os.path.basename(file_path_next))[0]}_diff.png"
    # output_path = os.path.join(output_dir, output_filename)
    # plt.savefig(output_path, dpi=200, bbox_inches='tight')
    # plt.close(fig)  # 关闭图形以清理内存

    # 手动清理不再使用的变量
    del my_map_prev, my_map_next, my_submap_prev, my_submap_next
    del normalized_map_prev, normalized_map_next, aligned_map_prev, aligned_map_next
    del diff_data, diff_map