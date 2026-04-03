# -*- coding: utf-8 -*-
"""
Created on Wed Mar  5 21:51:43 2025

@author: 李
"""

import os
import gc
import time
import sunpy.map
import matplotlib.pyplot as plt
import astropy.units as u
import matplotlib.colors as colors
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm

# 配置参数
vmin = -6
vmax = 4
norm = colors.Normalize(vmin=vmin, vmax=vmax)
data_dir = '<PROJECT_ROOT>/20250503/All/304/'
# 差分图像输出目录
output_dir_base = '<PROJECT_ROOT>/20250503/All/304'
os.makedirs(output_dir_base, exist_ok=True)

# 文件范围设置
start_idx = 50    # 起始索引（包含）
end_idx = 150     # 结束索引（不包含）

# 差分方法设置：'base'（与第一个帧差分）、'running'（与前一帧差分）、None（不使用差分）
diff_method = 'running'  # 可在此处切换差分方法

# 获取所有FITS文件路径并排序
file_paths = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith('.fits')]
file_paths.sort()

# 检查文件范围有效性
if len(file_paths) == 0:
    raise ValueError("数据目录中没有找到FITS文件！")
if start_idx < 0:
    raise ValueError("起始索引不能小于0！")
if end_idx > len(file_paths):
    raise ValueError(f"结束索引不能超过文件总数（共{len(file_paths)}个文件）！")
if start_idx >= end_idx:
    raise ValueError("起始索引必须小于结束索引！")

selected_files = file_paths[start_idx:end_idx]
total_files = len(selected_files)
print(f"已选择处理 {total_files} 个文件（从索引 {start_idx} 到 {end_idx-1}）")

# 定义固定的坐标值
roi_tx1, roi_ty1 = -700 * u.arcsec, -100 * u.arcsec  # 左下坐标
roi_tx2, roi_ty2 = -100 * u.arcsec, 400 * u.arcsec  # 右上坐标

# 先加载所有文件并预处理
print("正在加载并预处理所有文件...")
m_seq = []
for file_path in tqdm(selected_files, desc="Loading files", unit="File"):
    try:
        # 读取FITS文件并创建sunpy map
        current_map = sunpy.map.Map(file_path)
        
        # 归一化处理：除以曝光时间
        normalized_data = current_map.data / current_map.exposure_time
        normalized_map = sunpy.map.Map(normalized_data, current_map.meta)
        
        # 裁剪到固定区域
        with propagate_with_solar_surface():
            current_frame = normalized_map.coordinate_frame
            roi_bottom_left = SkyCoord(Tx=roi_tx1, Ty=roi_ty1, frame=current_frame)
            roi_top_right = SkyCoord(Tx=roi_tx2, Ty=roi_ty2, frame=current_frame)
            cutout_map = normalized_map.submap(roi_bottom_left, top_right=roi_top_right)
        
        m_seq.append(cutout_map)
        
    except Exception as e:
        print(f"\n加载文件出错 : {file_path} : {str(e)}")
        continue

# 根据差分方法处理序列
if diff_method == 'base' and len(m_seq) > 1:
    # 与第一个帧进行差分
    diff_maps = sunpy.map.Map([m - m_seq[0].quantity for m in m_seq[1:]], sequence=True)
    output_dir = os.path.join(output_dir_base, 'base_diff/')
    os.makedirs(output_dir, exist_ok=True)
    print(f"使用基准差分方法，共生成 {len(diff_maps)} 个差分图像")
    
elif diff_method == 'running' and len(m_seq) > 1:
    # 与前一帧进行差分（滑动差分）
    diff_maps = sunpy.map.Map(
        [m - prev_m.quantity for m, prev_m in zip(m_seq[1:], m_seq[:-1])],
        sequence=True
    )
    output_dir = os.path.join(output_dir_base, 'running_diff/')
    os.makedirs(output_dir, exist_ok=True)
    print(f"使用滑动差分方法，共生成 {len(diff_maps)} 个差分图像")
    
elif diff_method is None:
    # 不使用差分，直接使用原始裁剪图像
    diff_maps = m_seq
    output_dir = os.path.join(output_dir_base, 'original/')
    os.makedirs(output_dir, exist_ok=True)
    print(f"不使用差分，共生成 {len(diff_maps)} 个图像")
    
else:
    raise ValueError("无效的差分方法！请选择 'base'、'running' 或 None")

# 处理并保存差分图像
start_time = time.time()
for i, diff_map in tqdm(enumerate(diff_maps), desc="Processing diffs", total=len(diff_maps)):
    try:
        # 绘制图像
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(projection=diff_map)
        
        # 绘制差分图像，使用不同的colormap以区分原始图像
        cmap ='sdoaia304'
        im = diff_map.plot(axes=ax, cmap=cmap, norm=norm)
        
        # 设置标题（提取时间戳）
        if diff_method == 'base':
            # 基准差分：当前帧 - 第0帧
            base_name = os.path.basename(selected_files[i+1])
            base_time = os.path.basename(selected_files[0]).split('.')[2]
            current_time = base_name.split('.')[2]
            ax.set_title(f"{current_time}", fontsize=12)
        elif diff_method == 'running':
            # 滑动差分：当前帧 - 前一帧
            curr_name = os.path.basename(selected_files[i+1])
            prev_name = os.path.basename(selected_files[i])
            curr_time = curr_name.split('.')[2]
            prev_time = prev_name.split('.')[2]
            ax.set_title(f"{curr_time}", fontsize=12)
        else:
            # 原始图像
            base_name = os.path.basename(selected_files[i])
            time_str = base_name.split('.')[2]
            ax.set_title(f"{time_str}", fontsize=12)
        
        # 保存图像
        if diff_method == 'base':
            output_filename = f"diff_base_{i+1:04d}.png"
        elif diff_method == 'running':
            output_filename = f"diff_running_{i+1:04d}.png"
        else:
            output_filename = f"{os.path.splitext(os.path.basename(selected_files[i]))[0]}.png"
            
        output_path = os.path.join(output_dir, output_filename)
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.show()  # 如需实时显示，取消注释
        
        # 清理资源
        plt.close(fig)
        del diff_map, ax, fig, im
        gc.collect()
        
    except Exception as e:
        print(f"\n处理差分图像出错 : {i} : {str(e)}")
        plt.close('all')
        gc.collect()
        continue

total_time = time.time() - start_time
print(f"\n处理完成！共处理 {len(diff_maps)} 个图像，耗时 {total_time:.2f} 秒")