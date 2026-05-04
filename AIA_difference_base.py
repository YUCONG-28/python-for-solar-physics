# -*- coding: utf-8 -*-
# 模块用途: 生成 SDO/AIA 基准差分图像，用事件前参考帧突出后续 EUV 亮度变化。
# 主要输入: 时间排序后的 AIA FITS 序列和基准帧设置。
# 主要输出/运行说明: 输出差分 PNG 图像，适合耀斑或喷流前后对比分析。
"""
Created on Wed Sep 17 14:20:20 2025

@author: Severus
"""

import gc
import time
from pathlib import Path

import astropy.units as u
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import sunpy.map
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm

vmin = -888
vmax = 888
norm = colors.Normalize(vmin=vmin, vmax=vmax)
data_dir = Path("D:/Flare/JSOCdata/All/AIA_131_pro/")
output_dir = Path("D:/Flare/JSOCdata/All/AIA_131_pro/difference_two_plot_min/")
output_dir.mkdir(parents=True, exist_ok=True)

start_idx = 99
end_idx = 200  # 不包含

file_paths = [p for p in data_dir.iterdir() if p.suffix == ".fits"]
file_paths.sort()

sliced_files = file_paths[start_idx:end_idx]

if len(sliced_files) < 2:
    raise ValueError(
        f"选取的文件范围需要至少2个文件，当前仅找到{len(sliced_files)}个文件!"
    )

total_files = len(sliced_files)
print(f"在选取的范围内找到 {total_files} 个FITS文件，准备开始处理...")

try:
    base_map = sunpy.map.Map(sliced_files[0])

    base_normalized_data = base_map.data / base_map.exposure_time
    base_normalized_map = sunpy.map.Map(base_normalized_data, base_map.meta)

    roi_bottom_left = SkyCoord(
        Tx=180 * u.arcsec,
        Ty=-340 * u.arcsec,
        frame=base_normalized_map.coordinate_frame,
    )
    roi_top_right = SkyCoord(
        Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=base_normalized_map.coordinate_frame
    )
    base_cutout_map = base_normalized_map.submap(
        roi_bottom_left, top_right=roi_top_right
    )
    target_wcs = base_cutout_map.wcs

    with propagate_with_solar_surface():
        base_aligned_map = base_cutout_map.reproject_to(target_wcs)
    base_data = base_aligned_map.data

    base_processed_map = sunpy.map.Map(base_data, base_aligned_map.meta)
    fig = plt.figure()
    ax = fig.add_subplot(projection=base_processed_map)
    base_processed_map.plot(axes=ax, cmap="sdoaia131", norm=norm)

    base_name = sliced_files[0].name
    output_path = output_dir / f"{base_name}.png"
    base_time_str = base_name.split(".")[2]
    plt.title(f"{base_time_str}")

    # plt.savefig(str(output_path), dpi=300, bbox_inches='tight')
    plt.show()
    # plt.close(fig)

    del base_map, base_normalized_data, base_normalized_map, base_cutout_map
    del base_processed_map, base_aligned_map, ax, fig
    gc.collect()

except Exception as e:
    print(f"处理基准文件出错: {sliced_files[0]} : {str(e)}")
    raise

start_time = time.time()
for i in tqdm(range(1, total_files), desc="Processing", unit="File"):
    try:

        current_file = sliced_files[i]
        current_map = sunpy.map.Map(current_file)

        current_normalized_data = current_map.data / current_map.exposure_time
        current_normalized_map = sunpy.map.Map(
            current_normalized_data, current_map.meta
        )

        current_cutout_map = current_normalized_map.submap(
            roi_bottom_left, top_right=roi_top_right
        )

        with propagate_with_solar_surface():
            current_aligned_map = current_cutout_map.reproject_to(target_wcs)
        current_data = current_aligned_map.data

        if base_data.shape != current_data.shape:
            raise ValueError(f"数据维度不匹配: 文件 {i} 与基准文件维度不同")

        processed_data = current_data - base_data

        processed_map = sunpy.map.Map(processed_data, current_aligned_map.meta)

        fig = plt.figure()
        ax = fig.add_subplot(projection=processed_map)
        processed_map.plot(axes=ax, cmap="sdoaia131", norm=norm)

        current_name = current_file.name
        output_path = output_dir / f"{current_name}_diff_from_base.png"

        current_time_str = current_name.split(".")[2]
        plt.title(f"{current_time_str}")

        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.show()
        plt.close(fig)

        del (
            current_map,
            current_normalized_data,
            current_normalized_map,
            current_cutout_map,
        )
        del current_aligned_map, current_data, processed_map, ax, fig, processed_data
        gc.collect()

    except Exception as e:
        print(f"\n处理文件出错: 当前文件 {current_file} : {str(e)}")
        plt.close("all")
        gc.collect()
        continue

total_time = time.time() - start_time
print(
    f"\n完成！选取范围内的文件数: {total_files} , 与基准文件的差分对数: {total_files - 1} , 总耗时: {total_time:.2f} 秒"
)
