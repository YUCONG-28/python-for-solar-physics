# -*- coding: utf-8 -*-
"""
Created on Fri Mar 13 16:35:42 2026

@author: Lee
"""

import os

def rename_fits_files(directory, prefix="aia.lev1_euv_12s"):
    """
    为指定文件夹下的 FITS 文件批量添加前缀
    """
    # 检查路径是否存在
    if not os.path.exists(directory):
        print(f"错误: 找不到文件夹 '{directory}'")
        return

    count = 0
    # 遍历文件夹内的所有文件
    for filename in os.listdir(directory):
        # 匹配以 .2025 开头的文件（或者根据你的需求匹配所有 .fits）
        if filename.startswith(".2025") and filename.endswith(".fits"):
            
            # 构建新文件名
            new_name = f"{prefix}{filename}"
            
            # 获取完整路径
            old_path = os.path.join(directory, filename)
            new_path = os.path.join(directory, new_name)

            # 执行重命名
            try:
                os.rename(old_path, new_path)
                print(f"已重命名: {filename} -> {new_name}")
                count += 1
            except Exception as e:
                print(f"重命名 {filename} 失败: {e}")

    print(f"\n操作完成！共重命名了 {count} 个文件。")

# --- 使用设置 ---
# 将下面的路径替换为你存放文件的实际文件夹路径
target_folder = 'D:/spike_topping_type_III/2025/20250124/All/171/2'
rename_fits_files(target_folder)