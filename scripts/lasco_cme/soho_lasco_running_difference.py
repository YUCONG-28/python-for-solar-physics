# -*- coding: utf-8 -*-
# 模块用途: 生成 SOHO/LASCO 运行差分图像以突出 CME 传播结构。
# 主要输入: 时间排序的 LASCO FITS 图像序列。
# 主要输出/运行说明: 输出差分日冕图，用于 CME 前沿追踪。
"""
Created on Tue Sep 30 07:51:10 2025

@author: Severus
"""

import re
from datetime import datetime
from pathlib import Path

import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np
from sunpy.map import Map

from solar_toolkit.path_config import load_script_config

# --------------------------
# 配置参数（请根据实际情况修改）
# --------------------------
PATH_CONFIG = load_script_config(
    "soho_lasco_running_difference",
    {"input_dir": "D:/LASCO/data/", "output_dir": "D:/LASCO/difference_plot/"},
)
input_dir = Path(PATH_CONFIG["input_dir"])  # 输入数据目录
output_dir = Path(PATH_CONFIG["output_dir"])  # 输出图像目录
vmin = -49  # 颜色映射最小值
vmax = 49  # 颜色映射最大值
recursive = True  # 是否递归查找子目录中的.jp2文件
# --------------------------


def setup_chinese_font():
    """简化字体设置，避免不必要的警告"""
    plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常
    # 若需中文显示，可手动指定系统存在的字体（如Windows的SimHei）
    try:
        plt.rcParams["font.family"] = ["SimHei"]
    except:
        pass


def extract_timestamp_from_filename(filename):
    """从文件名中提取时间戳（适配常见LASCO文件名格式，如LASCO_C2_20240808_223600.jp2）"""
    # 正则表达式：匹配14位时间戳（YYYYMMDDHHMMSS）或12位（YYYYMMDDHHMM）
    time_pattern = r"(\d{8}_\d{4,6})"  # 匹配"20240808_2236"或"20240808_223600"
    match = re.search(time_pattern, filename)
    if match:
        time_str = match.group(1)
        # 适配不同时间戳长度（补全为14位）
        if len(time_str.replace("_", "")) == 12:  # YYYYMMDDHHMM
            time_str += "00"  # 补全为YYYYMMDDHHMMSS
        try:
            # 转换为datetime对象（用于正确排序）
            return datetime.strptime(time_str, "%Y%m%d_%H%M%S")
        except:
            pass
    # 若提取失败，返回默认时间（避免排序错误）
    return datetime.min


def get_jp2_files(input_dir, recursive=True):
    """获取所有.jp2文件（大小写不敏感，支持递归查找）"""
    if recursive:
        # 递归查找所有子目录
        pattern = "**/*.[jJ][pP]2"
    else:
        # 仅查找当前目录
        pattern = "*.[jJ][pP]2"

    # 获取所有匹配文件
    files = sorted(input_dir.glob(pattern))

    # 按文件名中的时间戳排序（确保顺序正确）
    files_sorted = sorted(files, key=lambda x: extract_timestamp_from_filename(x.name))

    return files_sorted


def main():
    setup_chinese_font()

    # 忽略sunpy元数据警告，保留关键错误
    import warnings

    warnings.filterwarnings("ignore", category=UserWarning, module="sunpy.map.mapbase")

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取所有.jp2文件（解决匹配遗漏和排序问题）
    files = get_jp2_files(input_dir, recursive=recursive)

    # 2. 打印找到的文件列表（关键：排查是否有文件遗漏）
    print(f"=== 共找到 {len(files)} 个.jp2文件 ===")
    for idx, file in enumerate(files, 1):
        print(f"{idx:2d}. {file.name}")
    print("=" * 50)

    # 检查文件数量
    if len(files) < 2:
        print(f"错误：仅找到{len(files)}个JP2文件，至少需要2个文件进行差分处理")
        return

    print(f"开始处理差分图像（共{len(files)-1}组相邻文件）...")
    norm = colors.Normalize(vmin=vmin, vmax=vmax)

    # 循环处理相邻文件对
    for i in range(1, len(files)):
        prev_file = files[i - 1]
        curr_file = files[i]
        prev_basename = prev_file.name
        curr_basename = curr_file.name

        try:
            # 3. 增强文件读取的错误处理（打印详细错误）
            print(f"\n处理第{i}组：{prev_basename} -> {curr_basename}")
            prev_map = Map(prev_file)
            curr_map = Map(curr_file)

            # 检查数据维度
            if prev_map.data.shape != curr_map.data.shape:
                print(
                    f"警告：{prev_basename}与{curr_basename}维度不匹配（{prev_map.data.shape} vs {curr_map.data.shape}），跳过"
                )
                continue

            # 计算差分数据
            diff_data = curr_map.data - prev_map.data
            diff_map = Map(diff_data, curr_map.meta)

            # 绘制黑白差分图
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(projection=diff_map)
            im = diff_map.plot(axes=ax, norm=norm, cmap="gray")  # 黑白对比映射

            # 添加颜色条
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label("差分强度")

            # 构建输出文件名（保留时间戳，便于追溯）
            curr_base = curr_file.stem
            output_path = output_dir / f"diff_bw_{curr_base}.png"

            # 保存图像（先关闭plt.show()，避免弹窗阻塞；如需预览可保留）
            plt.show()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            print(f"成功保存：{output_path.name}")

            plt.close(fig)

        except Exception as e:
            # 4. 详细错误日志（定位具体哪个文件读取失败）
            print(
                f"错误：处理{prev_basename}与{curr_basename}时失败 -> {type(e).__name__}: {str(e)}"
            )
            continue

    print("\n所有文件处理完成！")


if __name__ == "__main__":
    main()
