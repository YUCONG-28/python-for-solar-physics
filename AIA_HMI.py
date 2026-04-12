# -*- coding: utf-8 -*-
"""
Created on Thu Oct 23 21:26:10 2025

@author: Severus
"""

import os
import datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.lines import Line2D
import time
from tqdm import tqdm

# 导入共享工具模块
import utils_solar as utils

# 设置中文字体
utils.setup_chinese_font()

# 数据路径设置
input_dir_AIA = '<PROJECT_ROOT>/20250503/All/171'
input_dir_HMI = '<PROJECT_ROOT>/20250503/All/hmi'
output_dir = '<PROJECT_ROOT>/20250503/All/171_hmi'
os.makedirs(output_dir, exist_ok=True)

# 设置参数
threshold = 0 * u.Gauss  # HMI数据阈值，设置最小值
sigma = 3  # 高斯滤波标准差，越大越平滑
vmin = 16  # 最小值（对数尺度）
vmax = 6666  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)


# 获取排序后的文件列表
print("加载AIA文件...")
aia_files = utils.get_sorted_fits_files(input_dir_AIA)
print("加载HMI文件...")
hmi_files = utils.get_sorted_fits_files(input_dir_HMI)

if not aia_files:
    raise ValueError("AIA目录中未找到有效的FITS文件")
if not hmi_files:
    raise ValueError("HMI目录中未找到有效的FITS文件")

print(f"找到 {len(aia_files)} 个AIA文件和 {len(hmi_files)} 个HMI文件")

# 确定AIA的目标坐标系（与AIA_193.py保持一致）
if len(aia_files) >= 2:
    # 只加载第二个文件确定裁剪区域和目标坐标系
    temp_map = sunpy.map.Map(aia_files[1][0])
    roi_bottom_left = SkyCoord(Tx=-700 * u.arcsec, Ty=-100 * u.arcsec, frame=temp_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=-100 * u.arcsec, Ty=400 * u.arcsec, frame=temp_map.coordinate_frame)
    cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
    target_wcs = cutout_map.wcs  # 保存目标坐标系用于重投影
    
    # 立即清理临时变量释放内存
    utils.safe_delete(['temp_map', 'cutout_map', 'roi_bottom_left', 'roi_top_right'], locals())
else:
    raise ValueError("AIA文件数量不足，无法确定目标坐标系")


# 时间匹配并绘制图像
hmi_idx = 0  # HMI索引（滑动窗口）
total_files = len(aia_files)
start_time = time.time()
processed_files = 0

# 预定义轮廓线参数以避免重复创建
levels = utils.create_magnetic_contour_levels(50 * u.Gauss)
linewidths = [1, 1]  # 绝对值大的磁场（500G）用更粗的线
colors_list = ['b', 'r']  # 轮廓线颜色

# 创建图例元素一次，避免重复创建
legend_elements = [
    Line2D([0], [0], color='b', lw=1, alpha=0.8, label='-50 Gauss'),
    Line2D([0], [0], color='r', lw=1, alpha=0.8, label='50 Gauss')
]

# 监控内存使用
utils.monitor_memory_usage("处理开始前内存使用")

for aia_path, aia_time in tqdm(aia_files, desc="处理进度", unit="文件"):
    if hmi_idx >= len(hmi_files):
        print("已处理完所有HMI文件，终止程序")
        break

    file_start_time = time.time()
    
    # 滑动窗口寻找最近的HMI文件
    while hmi_idx < len(hmi_files) - 1:
        current_hmi_time = hmi_files[hmi_idx][1]
        next_hmi_time = hmi_files[hmi_idx + 1][1]
        current_diff = abs((aia_time - current_hmi_time).total_seconds())
        next_diff = abs((aia_time - next_hmi_time).total_seconds())
        if next_diff < current_diff:
            hmi_idx += 1
        else:
            break

    # 检查时间差
    hmi_path, hmi_time = hmi_files[hmi_idx]
    time_diff = abs((aia_time - hmi_time).total_seconds())
    if time_diff > 24:
        print(f"AIA文件 {os.path.basename(aia_path)} 无匹配HMI（时间差{time_diff:.1f}s），跳过")
        processed_files += 1
        continue

    # 绘制图像
    try:
        # 处理AIA数据（使用与AIA_193.py一致的重投影方式）
        try:
            # 加载AIA文件并归一化
            aia_map = sunpy.map.Map(aia_path)
            normalized_aia_map = utils.normalize_aia_exposure(aia_map)
            
            # 重投影到目标坐标系
            aligned_aia_map = utils.align_maps_to_reference(normalized_aia_map, target_wcs)
        except Exception as e:
            print(f"AIA文件读取失败：{aia_path}，错误：{e}")
            processed_files += 1
            continue
            
        # 处理HMI数据
        try:
            hmi_map = sunpy.map.Map(hmi_path)
            
            # HMI数据重投影到目标坐标系
            aligned_hmi_map = utils.align_maps_to_reference(hmi_map, target_wcs)
        
        except Exception as e:
            print(f"HMI文件读取失败：{hmi_path}，错误：{e}")
            processed_files += 1
            continue
            
        # 应用阈值和高斯滤波
        hmi_smoothed = utils.process_hmi_magnetic_field(aligned_hmi_map, threshold, sigma)

        # 绘制图像
        fig, ax = utils.create_figure_with_white_background(figsize=(10, 8))
        ax = fig.add_subplot(projection=aligned_aia_map)
        aligned_aia_map.plot(axes=ax, norm=norm)
        aligned_aia_map.draw_grid(axes=ax)

        # 绘制轮廓线
        cset = hmi_smoothed.draw_contours(
            levels, axes=ax, 
            colors=colors_list,
            alpha=0.8,
            filled=False, 
            linewidths=linewidths
        )
        ax.axis(ax.axis())  # 保持坐标范围

        # 添加图例
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1), frameon=True)

        # 设置标题
        title_time = utils.format_time_for_display(aia_time)
        ax.set_title(f"{title_time}", fontsize=16, pad=34)
        
        # 保存图像
        file_time_str = utils.format_time_for_filename(aia_time)
        output_path = os.path.join(output_dir, f"{file_time_str}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.show()
        
        # 关闭图像并清理内存
        plt.close(fig)
        utils.safe_delete(['aia_map', 'normalized_aia_map', 'aligned_aia_map',
                          'hmi_map', 'aligned_hmi_map', 'hmi_smoothed', 'ax', 'fig'], locals())
        
    except Exception as e:
        print(f"处理文件时出错: {e}")
        plt.close('all')
        utils.optimized_gc_collect()
    
    processed_files += 1
    
    # 每处理10个文件报告一次进度和内存使用
    if processed_files % 10 == 0:
        elapsed = time.time() - start_time
        files_per_second = processed_files / elapsed if elapsed > 0 else 0
        utils.monitor_memory_usage(f"已处理 {processed_files}/{total_files} 个文件")
        print(f"处理速度: {files_per_second:.2f} 文件/秒")

# 显示总耗时
total_time = time.time() - start_time
utils.monitor_memory_usage("处理完成后内存使用")
print(f"处理完成！共处理 {processed_files} 个文件，耗时: {total_time:.2f} 秒")
print(f"平均处理速度: {processed_files/total_time:.2f} 文件/秒")
