# -*- coding: utf-8 -*-
# 模块用途: 从 AIA EUV FITS 图像序列中提取光变/流量数据。
# 主要输入: AIA FITS 序列、目标区域和波段配置。
# 主要输出/运行说明: 输出表格化光变数据，供后续绘图和多波段时间分析使用。
"""
Created on Fri Oct 10 21:37:15 2025

@author: Severus
"""

import csv
import re
import time
from datetime import datetime
from pathlib import Path

import astropy.units as u
import numpy as np
import sunpy.map
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm

# 配置参数
data_dir = Path("D:/Flare/JSOCdata/All/AIA_1600/")
output_dir = Path("D:/Flare/JSOCdata/All/Flux_data/")
output_dir.mkdir(parents=True, exist_ok=True)
data_file = output_dir / "aia_1600_the third region.csv"  # 数据存储路径


def load_stored_data():
    """从CSV文件加载已存储的数据"""
    if not data_file.exists():
        return None, None

    time_list = []
    sum_data_list = []
    try:
        with data_file.open("r", encoding="utf-8") as f:
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
        with data_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "flux"])  # 表头
            for dt, flux in zip(time_list, sum_data_list):
                # 保存为字符串格式的时间
                writer.writerow([dt.strftime("%Y-%m-%d %H:%M:%S"), flux])
        print(f"数据已保存至: {data_file}")
    except Exception as e:
        print(f"保存数据失败: {str(e)}")


def process_fits_files():
    """处理FITS文件并返回时间和通量数据"""
    # 获取并排序FITS文件（不区分大小写）
    file_paths = [p for p in data_dir.iterdir() if p.suffix.lower() == ".fits"]
    file_paths.sort()
    total_files = min(600, len(file_paths))

    if total_files < 2:
        raise ValueError("文件数量不足，至少需要2个FITS文件！")

    # 确定裁剪区域
    target_wcs = None
    try:
        temp_map = sunpy.map.Map(file_paths[0])

        # 定义感兴趣区域（ROI）
        roi_bottom_left = SkyCoord(
            Tx=340 * u.arcsec, Ty=-240 * u.arcsec, frame=temp_map.coordinate_frame
        )
        roi_top_right = SkyCoord(
            Tx=420 * u.arcsec, Ty=-130 * u.arcsec, frame=temp_map.coordinate_frame
        )

        # 获取目标坐标系
        with propagate_with_solar_surface():
            cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
            target_wcs = cutout_map.wcs

        del temp_map, cutout_map
    except Exception as e:
        raise ValueError(f"初始化裁剪区域失败: {str(e)}") from e

    # 处理文件
    start_time = time.time()
    time_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{6}Z")
    time_list = []
    sum_data_list = []

    for i in tqdm(range(total_files), desc="处理进度", unit="文件"):
        try:
            current_map = sunpy.map.Map(file_paths[i])

            # 检查曝光时间有效性
            exposure_time = current_map.exposure_time
            if exposure_time <= 0:
                print(f"\n文件 {file_paths[i].name} 曝光时间无效，跳过")
                del current_map
                continue

            # 归一化处理
            normalized_data = current_map.data / exposure_time
            normalized_map = sunpy.map.Map(normalized_data, current_map.meta)

            # 重投影到目标坐标系
            with propagate_with_solar_surface():
                aligned_map = normalized_map.reproject_to(target_wcs)

            # 计算通量总和
            data_sum = np.sum(aligned_map.data)

            # 提取时间
            base_name = file_paths[i].name
            time_match = time_pattern.search(base_name)
            if not time_match:
                print(f"\n文件 {base_name} 时间格式不匹配，跳过")
                del current_map, normalized_map, aligned_map
                continue

            # 解析时间
            dt = datetime.strptime(time_match.group(), "%Y-%m-%dT%H%M%SZ")
            time_list.append(dt)
            sum_data_list.append(data_sum)

            # 手动释放资源
            del current_map, normalized_map, aligned_map
        except Exception as e:
            print(f"\n处理文件 {file_paths[i].name} 出错: {str(e)}")
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
        choice = (
            input("检测到已存储的数据，是否重新处理FITS文件？(y/n): ").strip().lower()
        )
        if choice != "y":
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
