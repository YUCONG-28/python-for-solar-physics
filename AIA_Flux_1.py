# -*- coding: utf-8 -*-
"""
Created on Sun Nov  2 21:10:40 2025

@author: Severus
"""

import os
import re
import time
import csv
import numpy as np
import sunpy.map
import astropy.units as u
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm
from datetime import datetime

# 配置参数
data_dir = 'D:/Flare/JSOCdata/All/AIA_1600/'
output_dir = 'D:/Flare/JSOCdata/All/Flux_data/'
os.makedirs(output_dir, exist_ok=True)
data_file = os.path.join(output_dir, 'aia_1600_selected_1.csv')  # 数据存储路径

def load_stored_data():
    """从CSV文件加载已存储的数据"""
    if not os.path.exists(data_file):
        return None, None
    
    time_list = []
    sum_data_list = []
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过表头
            for row in reader:
                if len(row) != 2:
                    continue
                # 解析时间和数据
                dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                flux = float(row[1])
                time_list.append(dt)
                sum_data_list.append(flux)		
        print(f"成功从 {data_file} 加载 {len(time_list)} 条数据")
        return time_list, sum_data_list
    except Exception as e:
        print(f"加载存储数据失败: {str(e)}")
        return None, None

def save_processed_data(time_list, sum_data_list):
    """将处理后的数据保存到CSV文件"""
    try:
        with open(data_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['time', 'flux'])  # 表头
            for dt, flux in zip(time_list, sum_data_list):
                # 保存为字符串格式的时间
                writer.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"), flux])
        print(f"数据已保存至: {data_file}")
    except Exception as e:
        print(f"保存数据失败: {str(e)}")

def process_fits_files():
    """处理FITS文件并返回时间和通量数据"""
    # 获取并排序FITS文件（不区分大小写）
    file_paths = []
    for f in os.listdir(data_dir):
        if f.lower().endswith('.fits'):
            file_paths.append(os.path.join(data_dir, f))
    file_paths.sort()
    total_files = min(600, len(file_paths))
    
    if total_files < 2:
        raise ValueError("文件数量不足，至少需要2个FITS文件！")
    
    # 定义感兴趣区域（ROI），来自AIA_selected_1中的target_regions_sky
    target_regions_sky = None
    try:
        temp_map = sunpy.map.Map(file_paths[0])
        target_regions_sky = [
            (SkyCoord(Tx=240*u.arcsec, Ty=-205*u.arcsec, frame=temp_map.coordinate_frame),
             SkyCoord(Tx=280*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)),
            
            (SkyCoord(Tx=280*u.arcsec, Ty=-180*u.arcsec, frame=temp_map.coordinate_frame),
             SkyCoord(Tx=310*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)), 
            
            (SkyCoord(Tx=310*u.arcsec, Ty=-150*u.arcsec, frame=temp_map.coordinate_frame),
             SkyCoord(Tx=330*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)), 
        ]
        del temp_map  # 释放临时地图资源
    except Exception as e:
        raise ValueError(f"初始化目标区域失败: {str(e)}") from e
    
    # 处理文件
    start_time = time.time()
    time_pattern = re.compile(r'\d{4}-\d{2}-\d{2}T\d{6}Z')
    time_list = []
    sum_data_list = []
    
    for i in tqdm(range(total_files), desc="处理进度", unit="文件"):
        try:
            current_map = sunpy.map.Map(file_paths[i])
            
            # 检查曝光时间有效性
            exposure_time = current_map.exposure_time
            if exposure_time <= 0:
                print(f"\n文件 {os.path.basename(file_paths[i])} 曝光时间无效，跳过")
                del current_map
                continue
            
            # 归一化处理
            normalized_data = current_map.data / exposure_time
            normalized_map = sunpy.map.Map(normalized_data, current_map.meta)
            
            # 计算所有区域的通量总和
            data_sum = 0.0
            with propagate_with_solar_surface():
                for (bottom_left, top_right) in target_regions_sky:
                    # 获取当前区域的子图
                    region_map = normalized_map.submap(bottom_left, top_right=top_right)
                    # 累加该区域的通量值
                    data_sum += np.sum(region_map.data)
            
            # 提取时间
            base_name = os.path.basename(file_paths[i])
            time_match = time_pattern.search(base_name)
            if not time_match:
                print(f"\n文件 {base_name} 时间格式不匹配，跳过")
                del current_map, normalized_map
                continue
            
            # 解析时间
            dt = datetime.strptime(time_match.group(), "%Y-%m-%dT%H%M%SZ")
            time_list.append(dt)
            sum_data_list.append(data_sum)
            
            # 手动释放资源
            del current_map, normalized_map, region_map
        except Exception as e:
            print(f"\n处理文件 {os.path.basename(file_paths[i])} 出错: {str(e)}")
            continue
    
    # 强制垃圾回收
    import gc
    gc.collect()
    
    # 输出处理统计
    total_time = time.time() - start_time
    print(f"处理完成！共处理 {len(time_list)} 个文件，耗时: {total_time:.2f} 秒")
    
    return time_list, sum_data_list

def main():
    # 检查是否有已存储的数据
    stored_time, stored_flux = load_stored_data()
    
    if stored_time and stored_flux:
        # 询问用户是否需要重新处理数据
        choice = input("检测到已存储的数据，是否重新处理FITS文件？(y/n): ").strip().lower()
        if choice != 'y':
            print("使用已有的数据，不进行重新处理")
            return
    
    # 处理数据
    print("开始处理FITS文件...")
    time_list, sum_data_list = process_fits_files()
    
    if time_list and sum_data_list:
        # 保存处理后的数据
        save_processed_data(time_list, sum_data_list)
    else:
        print("没有生成有效数据，无法保存")

if __name__ == "__main__":
    main()