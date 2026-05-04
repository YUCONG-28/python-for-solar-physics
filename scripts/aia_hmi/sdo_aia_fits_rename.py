# -*- coding: utf-8 -*-
# 模块用途: 批量规范化 AIA FITS 文件名，便于后续时间排序和流水线处理。
# 主要输入: 待整理的 AIA FITS 文件目录和命名规则。
# 主要输出/运行说明: 重命名或生成规范文件名清单；运行前应确认目标目录备份。
"""
Created on Fri Mar 13 16:35:42 2026

@author: Lee
"""

from pathlib import Path


def rename_fits_files(directory, prefix="aia.lev1_euv_12s"):
    """
    为指定文件夹下的 FITS 文件批量添加前缀
    """
    dir_path = Path(directory)
    # 检查路径是否存在
    if not dir_path.exists():
        print(f"错误: 找不到文件夹 '{directory}'")
        return

    count = 0
    # 遍历文件夹内的所有文件
    for filename in dir_path.iterdir():
        # 匹配以 .2025 开头的文件（或者根据你的需求匹配所有 .fits）
        if filename.name.startswith(".2025") and filename.suffix == ".fits":

            # 构建新文件名
            new_name = f"{prefix}{filename.name}"

            # 获取完整路径
            old_path = filename
            new_path = dir_path / new_name

            # 执行重命名
            try:
                old_path.rename(new_path)
                print(f"已重命名: {filename.name} -> {new_name}")
                count += 1
            except Exception as e:
                print(f"重命名 {filename.name} 失败: {e}")

    print(f"\n操作完成！共重命名了 {count} 个文件。")


# --- 使用设置 ---
# 将下面的路径替换为你存放文件的实际文件夹路径
target_folder = "D:/spike_topping_type_III/2025/20250124/All/171/2"
rename_fits_files(target_folder)
