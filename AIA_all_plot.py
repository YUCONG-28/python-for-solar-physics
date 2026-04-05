# -*- coding: utf-8 -*-
"""
Created on Thu Oct 30 11:47:47 2025

@author: Severus
"""

import os
import re
import datetime
import gc
import time
import sunpy.map
import matplotlib.pyplot as plt
import astropy.units as u
import matplotlib.colors as colors
import numpy as np
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm  # 用于显示进度条

# 修改字体设置部分
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示问题

# 定义所有AIA通道目录
input_dirs = {
    '94': '<DATA_ROOT>/JSOCdata/All/AIA_94/',
    '131': '<DATA_ROOT>/JSOCdata/All/AIA_131/',
    '171': '<DATA_ROOT>/JSOCdata/All/AIA_171/',
    '193': '<DATA_ROOT>/JSOCdata/All/AIA_193_pro/',
    '211': '<DATA_ROOT>/JSOCdata/All/AIA_211/',
    '304': '<DATA_ROOT>/JSOCdata/All/AIA_304/'
}

output_dir = '<DATA_ROOT>/JSOCdata/All/AIA_all_plot'
os.makedirs(output_dir, exist_ok=True)

# 配置绘图参数
vmin = 0.6  # 最小值（对数尺度）
vmax = 9999  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)

# 每个通道对应的颜色权重（用于合成RGB图像）
color_weights = {
    '94': (0.2, 0.6, 0.2),    # 绿色调
    '131': (0.1, 0.3, 0.9),   # 蓝色调（增强蓝色）
    '171': (0.2, 0.7, 0.1),   # 绿色调
    '193': (0.4, 0.4, 0.4),   # 灰色调
    '211': (0.3, 0.6, 0.1),   # 绿色调
    '304': (0.9, 0.2, 0.1)    # 红色调（增强红色）
}

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
                files.append((file_path, file_time, f))
            except ValueError as e:
                print(f"跳过文件（时间提取失败）：{e}")
            except Exception as e:
                print(f"处理文件时出错：{f}，错误：{e}")
    return sorted(files, key=lambda x: x[1])

def find_matching_files(ref_time, other_files, max_diff=2):
    """查找与参考时间差不超过max_diff秒的文件"""
    min_diff = datetime.timedelta(seconds=86400)  # 1天的秒数
    best_match = None
    
    for file_path, file_time, filename in other_files:
        diff = abs(file_time - ref_time)
        if diff <= datetime.timedelta(seconds=max_diff) and diff < min_diff:
            best_match = (file_path, file_time, filename)
            min_diff = diff
    
    return best_match

def normalize_data(data, exposure_time, vmin, vmax):
    """归一化数据到0-1范围"""
    if exposure_time <= 0:
        return np.zeros_like(data)
    
    # 除以曝光时间并应用对数归一化
    normalized = data / exposure_time
    normalized = np.clip(normalized, vmin, vmax)
    normalized = (normalized - vmin) / (vmax - vmin)  # 归一化到0-1范围
    return normalized

def process_and_plot(file_groups):
    """处理所有文件组并将所有AIA数据绘制在同一张图像中"""
    # 确定裁剪区域（使用第一个193文件）
    first_193_file = file_groups[0]['193'][0]
    temp_map = sunpy.map.Map(first_193_file)
    roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=temp_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=temp_map.coordinate_frame)
    cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
    target_wcs = cutout_map.wcs  # 保存目标坐标系用于重投影
    shape = cutout_map.data.shape  # 获取图像尺寸
    
    # 清理临时变量
    del temp_map, cutout_map, roi_bottom_left, roi_top_right
    gc.collect()
    
    start_time = time.time()
    
    # 初始化总RGB数组，用于累积所有数据
    total_rgb = np.zeros((shape[0], shape[1], 3), dtype=np.float32)
    
    # 处理所有文件组，累积数据到总RGB数组
    for group in tqdm(file_groups, desc="累积所有文件数据", unit="组"):
        try:
            # 处理每个通道的文件并叠加到总RGB图像
            for channel, (file_path, _, filename) in group.items():
                # 加载文件
                current_map = sunpy.map.Map(file_path)
                
                # 检查曝光时间是否有效
                if current_map.exposure_time <= 0:
                    print(f"警告：文件 {filename} 曝光时间为零或负值，跳过处理")
                    continue
                
                # 归一化处理
                normalized_data = normalize_data(
                    current_map.data, 
                    current_map.exposure_time,
                    vmin, vmax
                )
                normalized_map = sunpy.map.Map(normalized_data, current_map.meta)
                
                # 重投影到目标坐标系
                with propagate_with_solar_surface():
                    aligned_map = normalized_map.reproject_to(target_wcs)
                
                # 获取颜色权重并叠加到总RGB图像
                r_weight, g_weight, b_weight = color_weights[channel]
                total_rgb[..., 0] += aligned_map.data * r_weight  # 红色通道
                total_rgb[..., 1] += aligned_map.data * g_weight  # 绿色通道
                total_rgb[..., 2] += aligned_map.data * b_weight  # 蓝色通道
                
                # 清理内存
                del current_map, normalized_data, normalized_map, aligned_map
            gc.collect()
            
        except Exception as e:
            print(f"\n处理文件组时出错: {str(e)}")
            gc.collect()
            continue
    
    # 归一化总RGB图像到0-1范围
    max_val = np.max(total_rgb)
    if max_val > 0:
        total_rgb /= max_val
    total_rgb = np.clip(total_rgb, 0, 1)
    
    # 创建最终图像
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(111, projection=target_wcs)
    
    # 显示合成图像
    im = ax.imshow(total_rgb, origin='lower')
    
    # 添加标题和图例
    fig.suptitle(f"AIA 多波段所有数据合成图", fontsize=16)
    
    # 添加颜色说明图例
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='red', lw=4, label='AIA 304 (红色增强)'),
        Line2D([0], [0], color='blue', lw=4, label='AIA 131 (蓝色增强)'),
        Line2D([0], [0], color='green', lw=4, label='其他波段 (绿色调)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    # 调整布局并保存/显示
    plt.tight_layout()
    # output_path = os.path.join(output_dir, f"all_aia_combined.png")
    # plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    
    # 清理内存
    plt.close(fig)
    gc.collect()
    
    total_time = time.time() - start_time
    print(f"\n处理完成！共处理 {len(file_groups)} 组文件，耗时: {total_time:.2f} 秒")
    # print(f"合成图像已保存至: {output_path}")

def main():
    # 获取所有目录的文件和时间
    all_files = {}
    for channel, dir_path in input_dirs.items():
        print(f"正在加载 {channel} 通道的文件...")
        all_files[channel] = get_sorted_files_with_time(dir_path)
        print(f"找到 {len(all_files[channel])} 个有效的 {channel} 通道文件")
    
    # 以193通道为基准，找到所有匹配的文件组
    print("正在匹配文件组（时间差不超过2秒）...")
    file_groups = []
    ref_channel = '193'
    
    for ref_path, ref_time, ref_filename in all_files[ref_channel]:
        group = {ref_channel: (ref_path, ref_time, ref_filename)}
        match_count = 0
        
        # 查找其他通道的匹配文件
        for channel in input_dirs:
            if channel == ref_channel:
                continue
                
            match = find_matching_files(ref_time, all_files[channel])
            if match:
                group[channel] = match
                match_count += 1
        
        # 只有当至少匹配到其他2个通道时才保留该组
        if match_count >= 2:
            file_groups.append(group)
    
    print(f"找到 {len(file_groups)} 个有效的文件组")
    
    # 处理并绘图
    if file_groups:
        process_and_plot(file_groups)
    else:
        print("没有找到有效的文件组，无法绘图")

if __name__ == "__main__":
    main()