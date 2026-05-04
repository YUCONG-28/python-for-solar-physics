# 模块用途: 生成 SDO/AIA 运行差分图像，通过相邻帧相减突出短时标演化。
# 主要输入: 按观测时间排序的 AIA FITS 序列。
# 主要输出/运行说明: 输出运行差分图像，用于追踪传播结构和瞬态变化。
"""
Created on Tue Sep 16 22:26:19 2025

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
from tqdm import tqdm

vmin = -777
vmax = 777
norm = colors.Normalize(vmin=vmin, vmax=vmax)
# norm = colors.LogNorm()
data_dir = Path("<PROJECT_ROOT>/20250124/All/94/1/")
output_dir = Path("<PROJECT_ROOT>/20250124/All/94/1/differnce_plot/")
output_dir.mkdir(parents=True, exist_ok=True)

start_idx = 150
end_idx = 450  # 不包含

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
    first_map = sunpy.map.Map(sliced_files[0])

    first_normalized_data = first_map.data / first_map.exposure_time
    first_normalized_map = sunpy.map.Map(first_normalized_data, first_map.meta)

    roi_bottom_left = SkyCoord(
        Tx=600 * u.arcsec,
        Ty=-280 * u.arcsec,
        frame=first_normalized_map.coordinate_frame,
    )
    roi_top_right = SkyCoord(
        Tx=1210 * u.arcsec,
        Ty=100 * u.arcsec,
        frame=first_normalized_map.coordinate_frame,
    )
    first_cutout_map = first_normalized_map.submap(
        roi_bottom_left, top_right=roi_top_right
    )
    target_wcs = first_cutout_map.wcs

    # 删除消自转功能，直接重投影
    first_aligned_map = first_cutout_map.reproject_to(target_wcs)
    first_data = first_aligned_map.data

    first_processed_map = sunpy.map.Map(first_data, first_aligned_map.meta)
    fig = plt.figure()
    ax = fig.add_subplot(projection=first_processed_map)
    first_processed_map.plot(axes=ax, cmap="sdoaia94", norm=norm)

    first_name = sliced_files[0].name
    output_path = output_dir / f"{first_name}.png"
    time_str = first_name.split(".")[2]
    plt.title(f"{time_str}")

    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

    del first_map, first_normalized_data, first_normalized_map, first_cutout_map
    del first_processed_map, first_aligned_map, first_data, ax, fig
    gc.collect()

except Exception as e:
    print(f"处理第一个文件出错: {sliced_files[0]} : {str(e)}")
    raise

start_time = time.time()

for i in tqdm(range(1, total_files), desc="Processing", unit="File"):
    try:
        prev_file = sliced_files[i - 1]
        prev_map = sunpy.map.Map(prev_file)

        prev_normalized_data = prev_map.data / prev_map.exposure_time
        prev_normalized_map = sunpy.map.Map(prev_normalized_data, prev_map.meta)

        prev_cutout_map = prev_normalized_map.submap(
            roi_bottom_left, top_right=roi_top_right
        )

        # 删除消自转功能，直接重投影
        prev_aligned_map = prev_cutout_map.reproject_to(target_wcs)
        prev_data = prev_aligned_map.data

        current_file = sliced_files[i]
        current_map = sunpy.map.Map(current_file)
        current_normalized_data = current_map.data / current_map.exposure_time
        current_normalized_map = sunpy.map.Map(
            current_normalized_data, current_map.meta
        )
        current_cutout_map = current_normalized_map.submap(
            roi_bottom_left, top_right=roi_top_right
        )

        # 删除消自转功能，直接重投影
        current_aligned_map = current_cutout_map.reproject_to(target_wcs)
        current_data = current_aligned_map.data

        if prev_data.shape != current_data.shape:
            raise ValueError(f"数据维度不匹配: 文件 {i} 与前一个文件 {i-1} 维度不同")

        processed_data = current_data - prev_data

        processed_map = sunpy.map.Map(processed_data, current_aligned_map.meta)

        fig = plt.figure()
        ax = fig.add_subplot(projection=processed_map)
        processed_map.plot(axes=ax, cmap="sdoaia94", norm=norm)

        current_name = current_file.name
        output_path = output_dir / f"{current_name}_diff.png"
        prev_time_str = prev_file.name.split(".")[2]
        current_time_str = current_name.split(".")[2]
        plt.title(f"{current_time_str}")

        # plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.show()
        plt.close(fig)

        del prev_map, prev_normalized_data, prev_normalized_map, prev_cutout_map
        del prev_aligned_map, prev_data, current_map, current_normalized_data
        del current_normalized_map, current_cutout_map, current_aligned_map
        del current_data, processed_map, ax, fig, processed_data
        gc.collect()

    except Exception as e:
        print(f"\n处理文件对出错: 前一个 {prev_file}, 当前 {current_file} : {str(e)}")
        plt.close("all")
        gc.collect()
        continue

total_time = time.time() - start_time

print(
    f"\n完成！选取范围内的文件数: {total_files} , 处理差分对数: {total_files - 1} , 总耗时: {total_time:.2f} 秒"
)
