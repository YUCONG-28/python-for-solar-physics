#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Mar 19 20:34:49 2025

@author: zz
"""

import os
import imageio.v2 as imageio

fps=10
outname='/lasco02_3.mp4'

script_dir = os.path.dirname(os.path.abspath(__file__))
print(script_dir)

# 定义目录路径和文件匹配规则
directory = script_dir
target_suffix = ".png"

# 实时扫描目录，直接识别JP2文件并按修改时间排序
files = []
with os.scandir(directory) as entries:
    for entry in entries:
        if entry.is_file() and entry.name.endswith(target_suffix):
            files.append(entry)

sorted_files = sorted(files, key=lambda x: x.stat().st_mtime)

# 获取完整路径列表
filename = [os.path.join(directory, file.name) for file in sorted_files]

# 读取 PNG 文件
images = []
for fn in filename:
    images.append(imageio.imread(fn))
# 保存为 MP4 文件
output_file = script_dir + outname
imageio.mimwrite(output_file, images, fps=fps)  # fps 是帧率，可以根据需要调整

print(f"视频已保存为 {output_file}")





