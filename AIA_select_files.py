# -*- coding: utf-8 -*-
# 模块用途: 按目标观测时间筛选最接近的 AIA FITS 文件。
# 主要输入: AIA 文件目录和目标时间列表。
# 主要输出/运行说明: 复制或列出匹配文件，用于多仪器同步分析。
"""
Created on Thu Mar 12 23:10:15 2026

@author: Lee
"""

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path


def filter_and_copy_aia_files(
    src_base_dir, out_base_dir, target_time_str, tolerance_seconds=15
):
    src_path = Path(src_base_dir)
    out_path = Path(out_base_dir)

    # ================= 核心逻辑处理 =================
    # 1. 解析目标中心时间
    target_time = datetime.strptime(target_time_str, "%Y-%m-%dT%H%M%S")

    # 2. 自动计算搜索的时间窗口（中心时间 ± 容差秒数）
    dt_start = target_time - timedelta(seconds=tolerance_seconds)
    dt_end = target_time + timedelta(seconds=tolerance_seconds)

    print(f"目标中心时间: {target_time}")
    print(f"自动计算的搜索窗口: {dt_start} 至 {dt_end}")

    # 3. 自动生成目标文件夹路径 (例如把 043849 变成 0438_49)
    time_suffix = target_time.strftime("%H%M_%S")
    target_base_dir = out_path / time_suffix

    target_aia = target_base_dir / "AIA"
    target_rasis = target_base_dir / "RaSIS"
    target_rs = target_base_dir / "RS"

    # 自动创建所需文件夹
    for folder in [target_aia, target_rasis, target_rs]:
        folder.mkdir(parents=True, exist_ok=True)

    # 4. 正则表达式：同时提取时间和波段
    pattern = re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6})Z\.(\d+)\.")
    candidates = {}

    print("\n开始扫描并收集时间窗口内的文件...")
    for root in src_path.rglob("*"):
        if root.is_file() and root.suffix == ".fits":
            file = root.name
            match = pattern.search(file)
            if match:
                time_str = match.group(1)
                wave = match.group(2)  # 提取波段
                file_dt = datetime.strptime(time_str, "%Y-%m-%dT%H%M%S")

                # 如果在时间窗口内，则加入该波段的候选列表
                if dt_start <= file_dt <= dt_end:
                    if wave not in candidates:
                        candidates[wave] = []
                    candidates[wave].append((root, file, file_dt))

    copied_count = 0
    print("\n开始挑选每个波段最接近目标时间的文件并复制...")

    # 5. 遍历每个波段的候选文件，找出时间差最小的进行复制
    if not candidates:
        print(
            "警告：在指定的时间窗口内未找到任何符合条件的 AIA 文件，请检查时间或调大 tolerance_seconds。"
        )
        return

    for wave, file_list in candidates.items():
        best_file = min(
            file_list, key=lambda x: abs((x[2] - target_time).total_seconds())
        )

        src_file_path = best_file[0]
        file_name = best_file[1]
        dst_file_path = target_aia / file_name

        if not dst_file_path.exists():
            shutil.copy2(src_file_path, dst_file_path)
            print(
                f"波段 {wave:>4} | 选定时间: {best_file[2].strftime('%H:%M:%S')} | 成功复制: {file_name}"
            )
            copied_count += 1
        else:
            print(f"波段 {wave:>4} | 文件已存在，跳过: {file_name}")

    print(
        f"\n操作完成！共计为 {len(candidates)} 个波段挑选并复制了 {copied_count} 个 AIA 文件。"
    )
    print(f"文件已保存至: {target_aia}")


if __name__ == "__main__":
    # ================= 极简配置区域 =================
    # 每次只需要在这里修改中心时间和输出根目录即可！

    SOURCE_DIR = r"D:\spike_topping_type_III\2025\20250124\All"
    OUTPUT_BASE_DIR = r"D:\spike_topping_type_III\2025\20250124\DEM"

    # 你只需要修改这个时间
    TARGET_TIME = "2025-01-24T045710"

    # 容差秒数：比如 15 代表搜索 04:38:34 到 04:39:04 之间的文件
    TOLERANCE = 12

    filter_and_copy_aia_files(
        src_base_dir=SOURCE_DIR,
        out_base_dir=OUTPUT_BASE_DIR,
        target_time_str=TARGET_TIME,
        tolerance_seconds=TOLERANCE,
    )
