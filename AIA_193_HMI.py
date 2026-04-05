# -*- coding: utf-8 -*-
"""
Created on Thu Oct 23 21:26:10 2025

@author: Severus
"""

import os
import re
import datetime
import sunpy.map
import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from astropy.coordinates import SkyCoord
from scipy.ndimage import gaussian_filter
import time
import gc  # 引入垃圾回收模块
from tqdm import tqdm
from matplotlib.lines import Line2D  # 用于创建自定义图例

# 修改字体设置部分
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 数据路径设置
input_dir_AIA = 'D:/Flare/JSOCdata/All/AIA_193_pro/'
input_dir_HMI = 'D:/Flare/JSOCdata/All/HMI/'
output_dir = 'D:/Flare/JSOCdata/All/AIA_193_HMI'
os.makedirs(output_dir, exist_ok=True)

# 设置参数
threshold = 1 * u.Gauss  # HMI数据阈值
sigma = 4  # 高斯滤波标准差
vmin = 34  # 最小值（对数尺度）
vmax = 130000  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)


def extract_time_from_filename(filename):
    """从文件名提取时间信息"""
    # 匹配HMI文件名格式
    hmi_match = re.search(r'(\d{8}_\d{6})_TAI', filename)
    if hmi_match:
        time_str = hmi_match.group(1)
        return datetime.datetime.strptime(time_str, '%Y%m%d_%H%M%S')
    
    # 匹配AIA文件名格式（支持有冒号和无冒号两种）
    aia_match1 = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)', filename)
    if aia_match1:
        time_str = aia_match1.group(1)
        return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ')
    
    aia_match2 = re.search(r'(\d{4}-\d{2}-\d{2}T\d{6}Z)', filename)
    if aia_match2:
        time_str = aia_match2.group(1)
        return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H%M%SZ')
    
    aia_alt_match = re.search(r'(\d{8})T(\d{6})', filename)
    if aia_alt_match:
        time_str = f"{aia_alt_match.group(1)}_{aia_alt_match.group(2)}"
        return datetime.datetime.strptime(time_str, '%Y%m%d_%H%M%S')
    
    raise ValueError(f"无法从文件名提取时间：{filename}")


def get_sorted_files_with_time(input_dir):
    """获取目录下所有FITS文件并按时间排序"""
    files = []
    for f in os.listdir(input_dir):
        if f.lower().endswith('.fits'):
            try:
                file_path = os.path.join(input_dir, f)
                if os.path.getsize(file_path) < 1024:  # 跳过空文件
                    print(f"跳过空文件：{f}")
                    continue
                file_time = extract_time_from_filename(f)
                files.append((file_path, file_time))
            except ValueError as e:
                print(f"跳过文件（时间提取失败）：{e}")
            except Exception as e:
                print(f"处理文件时出错：{f}，错误：{e}")
    return sorted(files, key=lambda x: x[1])


# 获取排序后的文件列表
aia_files = get_sorted_files_with_time(input_dir_AIA)
hmi_files = get_sorted_files_with_time(input_dir_HMI)

if not aia_files:
    raise ValueError("AIA目录中未找到有效的FITS文件")
if not hmi_files:
    raise ValueError("HMI目录中未找到有效的FITS文件")

# 确定AIA的目标坐标系（与AIA_193.py保持一致）
if len(aia_files) >= 2:
    # 只加载第二个文件确定裁剪区域和目标坐标系
    temp_map = sunpy.map.Map(aia_files[1][0])
    roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=temp_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=temp_map.coordinate_frame)
    cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
    target_wcs = cutout_map.wcs  # 保存目标坐标系用于重投影
    
    # 立即清理临时变量释放内存
    del temp_map, cutout_map, roi_bottom_left, roi_top_right
    gc.collect()
else:
    raise ValueError("AIA文件数量不足，无法确定目标坐标系")


# 时间匹配并绘制图像
hmi_idx = 0  # HMI索引（滑动窗口）
total_files = len(aia_files)
start_time = time.time()
processed_files = 0

# 预定义轮廓线参数以避免重复创建
levels = [50, 500] * u.Gauss
levels = np.concatenate((-1 * levels[::-1], levels))  # 得到 [-500, -50, 50, 500]
linewidths = [2, 1, 1, 2]  # 绝对值大的磁场（500G）用更粗的线
colors_list = ['blue', 'cyan', 'orange', 'red']  # 轮廓线颜色

# 创建图例元素一次，避免重复创建
legend_elements = [
    Line2D([0], [0], color='cyan', lw=1, alpha=0.8, label='-50 Gauss'),
    Line2D([0], [0], color='blue', lw=2, alpha=0.8, label='-500 Gauss'),
    Line2D([0], [0], color='orange', lw=1, alpha=0.8, label='50 Gauss'),
    Line2D([0], [0], color='red', lw=2, alpha=0.8, label='500 Gauss')
]

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
            normalized_data = aia_map.data / aia_map.exposure_time
            normalized_aia_map = sunpy.map.Map(normalized_data, aia_map.meta)
            
            # 重投影到目标坐标系
            with sunpy.coordinates.propagate_with_solar_surface():
                aligned_aia_map = normalized_aia_map.reproject_to(target_wcs)
        except Exception as e:
            print(f"AIA文件读取失败：{aia_path}，错误：{e}")
            processed_files += 1
            continue
            
        # 处理HMI数据
        try:
            hmi_map = sunpy.map.Map(hmi_path)
            
            # HMI数据重投影到目标坐标系
            with sunpy.coordinates.propagate_with_solar_surface():
                aligned_hmi_map = hmi_map.reproject_to(target_wcs)
            
            # 关键修复：确保单位存在（HMI数据单位通常为Gauss）
            if aligned_hmi_map.unit is None:
                # 手动设置单位为高斯（G）
                aligned_hmi_map = sunpy.map.Map(aligned_hmi_map.data, aligned_hmi_map.meta)
                aligned_hmi_map.meta['bunit'] = 'G'  # 元数据中补充单位信息
                hmi_unit = u.Gauss
            else:
                hmi_unit = aligned_hmi_map.unit
            
            # 使用确认后的单位计算hmi_data
            hmi_data = aligned_hmi_map.data * hmi_unit
        
        except Exception as e:
            print(f"HMI文件读取失败：{hmi_path}，错误：{e}")
            processed_files += 1
            continue
            
        # 应用阈值和高斯滤波
        hmi_data = aligned_hmi_map.data * aligned_hmi_map.unit
        hmi_data[np.abs(hmi_data) < threshold] = 0 * u.Gauss
        smoothed_data = gaussian_filter(hmi_data.value, sigma=sigma) * hmi_data.unit
        hmi_smoothed = sunpy.map.Map(smoothed_data, aligned_hmi_map.meta)

        # 绘制图像
        fig = plt.figure(figsize=(10, 8))
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
        ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.3, 1), frameon=True)

        # 设置标题
        title_time = aia_time.strftime('%Y-%m-%d %H:%M:%S')
        plt.title(f"{title_time}")
        
        # 保存图像
        file_time_str = aia_time.strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f"{file_time_str}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.show()
        
        # 关闭图像并清理内存
        plt.close(fig)
        del aia_map, normalized_data, normalized_aia_map, aligned_aia_map
        del hmi_map, aligned_hmi_map, hmi_data, smoothed_data, hmi_smoothed, ax, fig
        gc.collect()
        
    except Exception as e:
        print(f"处理文件时出错: {e}")
        plt.close('all')
        gc.collect()
    
    processed_files += 1

# 显示总耗时
total_time = time.time() - start_time
print(f"处理完成！共处理 {processed_files} 个文件，耗时: {total_time:.2f} 秒")