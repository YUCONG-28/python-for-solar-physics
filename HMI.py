# -*- coding: utf-8 -*-
"""
Created on Sun Mar 16 20:15:09 2025

@author: 李
"""

import os
import glob
import sunpy.map
import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import SkyCoord
from matplotlib.colors import Normalize
from sunpy.coordinates import frames

input_dir = 'D:/spike_topping_type_III/20250124/All/hmi/2'
output_dir = 'D:/spike_topping_type_III/20250124/All/hmi/2/plot'
os.makedirs(output_dir, exist_ok=True)

# 获取所有FITS文件并排序
fits_files = sorted(glob.glob(os.path.join(input_dir, "*.fits")))

# 显示文件信息
print(f"找到 {len(fits_files)} 个FITS文件")
print("文件列表:")
for i, file_path in enumerate(fits_files):
    print(f"{i:3d}: {os.path.basename(file_path)}")

# 用户选择文件范围
try:
    start_idx = int(input("\n请输入起始文件索引 (默认0): ") or 0)
    end_idx = int(input(f"请输入结束文件索引 (默认{len(fits_files)-1}): ") or len(fits_files)-1)
    
    # 验证索引范围
    start_idx = max(0, min(start_idx, len(fits_files)-1))
    end_idx = max(start_idx, min(end_idx, len(fits_files)-1))
    
    selected_files = fits_files[start_idx:end_idx+1]
    print(f"\n选择了 {len(selected_files)} 个文件进行处理 (索引 {start_idx} 到 {end_idx})")
    
except ValueError:
    print("输入无效，将处理所有文件")
    selected_files = fits_files

# 设置简洁的绘图风格
plt.style.use('default')

for file_path in selected_files:
    HMI_IMAGE = file_path
    my_map_0 = sunpy.map.Map(HMI_IMAGE)
    my_map = my_map_0.rotate(method='scipy')
    
    # 检查并修正坐标系
    print(f"处理文件: {os.path.basename(file_path)}")
    print(f"坐标系: {my_map.coordinate_frame}")
    print(f"数据形状: {my_map.data.shape}")
    
    # 定义感兴趣区域
    # 如果方向有问题，尝试交换坐标或使用不同的坐标值
    roi_top_right = SkyCoord(700*u.arcsec, -200*u.arcsec, frame=my_map.coordinate_frame)
    roi_bottom_left = SkyCoord(900*u.arcsec, 0*u.arcsec, frame=my_map.coordinate_frame)
    
    # 提取子图 - 不再使用transform_to
    my_submap = my_map.submap(roi_bottom_left, top_right=roi_top_right)
    
    # 创建图形
    fig = plt.figure(figsize=(8, 6))
    
    # 使用正确的投影
    ax = plt.subplot(projection=my_submap)
    
    # 正确设置归一化参数 - 通过 plot_settings
    # 首先检查是否已经有归一化设置
    if 'norm' in my_submap.plot_settings:
        # 如果有，更新它的 vmin 和 vmax
        my_submap.plot_settings['norm'].vmin = -1500
        my_submap.plot_settings['norm'].vmax = 1500
    else:
        # 如果没有，创建一个新的归一化对象
        my_submap.plot_settings['norm'] = Normalize(vmin=-1500, vmax=1500)
    
    # 绘制磁场图 - 使用适合HMI的配色
    im = my_submap.plot(
        axes=ax, 
        title=False, 
        cmap='hmimag'  # 专门为HMI磁图设计的色彩映射
    )
    
    # 添加颜色条
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Magnetic Field [G]', rotation=270, labelpad=15)
    
    # 设置坐标轴标签
    ax.set_xlabel('Helioprojective Longitude (Solar-X) [arcsec]')
    ax.set_ylabel('Helioprojective Latitude (Solar-Y) [arcsec]')
    
    # 移除网格
    ax.grid(False)
    
    # 添加标题
    obs_time = my_submap.date.strftime('%Y-%m-%d %H:%M:%S')
    ax.set_title(f'HMI Magnetogram - {obs_time}', fontsize=11, pad=10)
    
    # 绘制日面轮廓
    my_submap.draw_limb(axes=ax, color='black', linewidth=1.0)
    
    # 如果需要，可以添加方向标记（北箭头和东箭头）
    # 这有助于确认图像方向是否正确
    ax.set_autoscale_on(False)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图像
    output_filename = os.path.splitext(os.path.basename(file_path))[0] + '.png'
    output_path = os.path.join(output_dir, output_filename)
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.show()
    plt.close()  # 关闭图形以释放内存
    
    print(f"已生成: {output_filename}")

print(f"\n处理完成！共生成 {len(selected_files)} 张图像。")
print(f"输出目录: {output_dir}")