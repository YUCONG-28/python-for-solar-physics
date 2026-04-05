# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 23:40:00 2025

@author: Severus
"""

import os
import gc
import time
import sunpy.map
import numpy as np 
import matplotlib.pyplot as plt
import astropy.units as u
import matplotlib.colors as colors
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
from tqdm import tqdm
from matplotlib.patches import Polygon
from shapely.geometry import Polygon as ShapelyPolygon, LineString
from shapely.ops import unary_union
from shapely.validation import make_valid

# 配置参数
vmin = 6  # 最小值（对数尺度）
vmax = 666  # 最大值（对数尺度）
norm = colors.LogNorm(vmin=vmin, vmax=vmax)
data_dir = 'D:/Flare/JSOCdata/All/AIA_1600/'
output_dir = 'D:/Flare/JSOCdata/All/AIA_1600/plot_selected_1/'
os.makedirs(output_dir, exist_ok=True)

# 文件范围设置
start_idx = 0    # 起始索引（包含）
end_idx = 300     # 结束索引（不包含）

# 合并区域并只保留最外层轮廓（核心修改）
def merge_regions(regions):
    """将区域合并为只包含最外层轮廓的多边形，消除内部边界"""
    # 增大合并阈值以增强内部线条消除效果
    MERGE_THRESHOLD = 5e-3  # 比原阈值更大，促进内部线条融合
    SIMPLIFY_TOLERANCE = 1e-3  # 简化轮廓，去除冗余点
    
    polygons = []
    for xmin, ymin, width, height in regions:
        # 构建矩形多边形
        xmin, ymin = round(xmin, 6), round(ymin, 6)
        xmax = round(xmin + width, 6)
        ymax = round(ymin + height, 6)
        
        coords = [
            (xmin, ymin), (xmax, ymin), 
            (xmax, ymax), (xmin, ymax), 
            (xmin, ymin)  # 闭合
        ]
        poly = ShapelyPolygon(coords)
        if not poly.is_valid:
            poly = make_valid(poly)
        polygons.append(poly)
    
    # 关键修改1：合并所有多边形为单一 union，自动消除内部重叠边界
    union = unary_union(polygons)
    if not union.is_valid:
        union = make_valid(union)
    
    # 关键修改2：通过缓冲操作强化内部边界消除
    # 先膨胀再收缩，消除细小内部结构
    buffered = union.buffer(MERGE_THRESHOLD).buffer(-MERGE_THRESHOLD)
    if not buffered.is_valid:
        buffered = make_valid(buffered)
    
    # 关键修改3：只提取外边界，忽略所有内部孔洞
    merged = []
    if buffered.geom_type == 'Polygon':
        # 仅使用外轮廓，忽略内部孔洞
        exterior = buffered.exterior
        # 简化轮廓，去除不必要的点
        simplified_exterior = exterior.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
        merged_line = merge_close_segments(simplified_exterior, MERGE_THRESHOLD)
        merged.append(ShapelyPolygon(merged_line.coords))
    elif buffered.geom_type == 'MultiPolygon':
        for poly in buffered.geoms:
            exterior = poly.exterior
            simplified_exterior = exterior.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            merged_line = merge_close_segments(simplified_exterior, MERGE_THRESHOLD)
            merged.append(ShapelyPolygon(merged_line.coords))
    
    return merged

def merge_close_segments(line, threshold):
    """合并线段，确保轮廓连续光滑"""
    if not line:
        return line
    coords = list(line.coords)
    if len(coords) < 3:
        return line
    
    # 检查闭合环
    first = coords[0]
    last = coords[-1]
    is_closed = np.hypot(first[0] - last[0], first[1] - last[1]) < threshold
    
    # 合并近距离点
    merged_coords = [coords[0]]
    for i in range(1, len(coords)-1):
        dist = np.hypot(
            coords[i][0] - merged_coords[-1][0],
            coords[i][1] - merged_coords[-1][1]
        )
        if dist < threshold:
            continue
        merged_coords.append(coords[i])
    
    # 处理闭合状态
    if is_closed:
        merged_coords.append(merged_coords[0])  # 强制闭合
    else:
        merged_coords.append(coords[-1])
    
    return LineString(merged_coords)

# 框选样式（突出显示外层轮廓）
poly_style = {
    'edgecolor': 'red',
    'linewidth': 1.2,  # 加粗外轮廓
    'facecolor': 'none',
    'linestyle': '-',
    'zorder': 5,
    'antialiased': True,
}

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

# 加载参考文件确定裁剪区域和坐标转换
if len(file_paths) >= 2:
    temp_map = sunpy.map.Map(file_paths[1])
    
    # 目标区域定义（天球坐标）
    target_regions_sky = [
        (SkyCoord(Tx=240*u.arcsec, Ty=-205*u.arcsec, frame=temp_map.coordinate_frame),
         SkyCoord(Tx=280*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)),
        
        (SkyCoord(Tx=270*u.arcsec, Ty=-180*u.arcsec, frame=temp_map.coordinate_frame),
         SkyCoord(Tx=310*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)), 
        
        (SkyCoord(Tx=300*u.arcsec, Ty=-150*u.arcsec, frame=temp_map.coordinate_frame),
         SkyCoord(Tx=330*u.arcsec, Ty=-120*u.arcsec, frame=temp_map.coordinate_frame)), 
    ]

    # 定义裁剪区域
    roi_bottom_left = SkyCoord(Tx=180 * u.arcsec, Ty=-340 * u.arcsec, frame=temp_map.coordinate_frame)
    roi_top_right = SkyCoord(Tx=520 * u.arcsec, Ty=20 * u.arcsec, frame=temp_map.coordinate_frame)
    cutout_map = temp_map.submap(roi_bottom_left, top_right=roi_top_right)
    target_wcs = cutout_map.wcs

    # 转换为像素坐标
    target_regions_pixel = []
    for (bottom_left, top_right) in target_regions_sky:
        xmin, ymin = cutout_map.world_to_pixel(bottom_left)
        xmax, ymax = cutout_map.world_to_pixel(top_right)
        xmin, ymin, xmax, ymax = float(xmin.value), float(ymin.value), float(xmax.value), float(ymax.value)
        width = xmax - xmin
        height = ymax - ymin
        target_regions_pixel.append((xmin, ymin, width, height))

    # 执行区域合并（获取最外层轮廓）
    merged_polygons = merge_regions(target_regions_pixel)
    print(f"原始区域数量: {len(target_regions_sky)}, 合并后外层轮廓数量: {len(merged_polygons)}")

    # 清理内存
    del temp_map, cutout_map, roi_bottom_left, roi_top_right
    gc.collect()
else:
    raise ValueError("文件数量不足2个，无法确定裁剪区域！")

# 处理文件并显示进度
start_time = time.time()
for file_path in tqdm(selected_files, desc="processing", unit="File"):
    try:
        current_map = sunpy.map.Map(file_path)
        
        # 归一化处理
        normalized_data = current_map.data / current_map.exposure_time
        normalized_map = sunpy.map.Map(normalized_data, current_map.meta)
        
        # 重投影
        with propagate_with_solar_surface():
            aligned_map = normalized_map.reproject_to(target_wcs)
        
        # 绘制图像
        fig = plt.figure()
        ax = fig.add_subplot(projection=aligned_map)
        aligned_map.plot(axes=ax, cmap='sdoaia1600', norm=norm)
        
        # 绘制最外层轮廓（已无内部线条）
        for poly in merged_polygons:
            coords = list(poly.exterior.coords)
            polygon = Polygon(coords, **poly_style)
            ax.add_patch(polygon)
        
        # 保存或显示
        base_name = os.path.basename(file_path)
        output_path = os.path.join(output_dir, f"{base_name}.png")
        time_str = base_name.split('.')[2]
        plt.title(time_str)
        
        plt.savefig(output_path, dpi=300, bbox_inches='tight')  # 取消注释以保存
        plt.show()
        plt.close(fig)
        
        # 清理内存
        del current_map, normalized_data, normalized_map, aligned_map, ax, fig, polygon
        gc.collect()
        
    except Exception as e:
        print(f"\n处理文件出错 : {file_path} : {str(e)}")
        plt.close('all')
        gc.collect()
        continue

total_time = time.time() - start_time
print(f"\n处理完成！共处理 {total_files} 个文件，耗时 {total_time:.2f} 秒")