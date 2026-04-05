"""
AIA_slice.py
对选定时间的选定区域（任意形状）做切片，画出该区域随时间变化的图像。
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, PolygonSelector
import sunpy.map
from sunpy.net import Fido, attrs as a
from sunpy.time import parse_time
import astropy.units as u
from astropy.coordinates import SkyCoord
import os
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class RegionSelector:
    """
    交互式区域选择工具，支持矩形和多边形选择。
    """
    def __init__(self, image_data, extent=None):
        self.image_data = image_data
        self.extent = extent
        self.region_mask = None
        self.region_type = None
        self.coords = None
        
    def select_rectangle(self):
        """使用矩形选择区域"""
        fig, ax = plt.subplots()
        ax.imshow(self.image_data, origin='lower', extent=self.extent, cmap='sdoaia94')
        ax.set_title('单击并拖动以选择矩形区域')
        
        def onselect(eclick, erelease):
            x1, y1 = eclick.xdata, eclick.ydata
            x2, y2 = erelease.xdata, erelease.ydata
            self.coords = (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
            # 创建矩形掩模
            ny, nx = self.image_data.shape
            if self.extent is not None:
                xmin, xmax, ymin, ymax = self.extent
                dx = (xmax - xmin) / nx
                dy = (ymax - ymin) / ny
                x_vals = np.linspace(xmin + dx/2, xmax - dx/2, nx)
                y_vals = np.linspace(ymin + dy/2, ymax - dy/2, ny)
            else:
                x_vals = np.arange(nx)
                y_vals = np.arange(ny)
            xx, yy = np.meshgrid(x_vals, y_vals)
            self.region_mask = (xx >= self.coords[0]) & (xx <= self.coords[1]) & \
                               (yy >= self.coords[2]) & (yy <= self.coords[3])
            self.region_type = 'rectangle'
            plt.close(fig)
        
        rect_selector = RectangleSelector(ax, onselect, useblit=True,
                                          button=[1], minspanx=5, minspany=5,
                                          spancoords='data', interactive=True)
        plt.show()
        return self.region_mask, self.coords
    
    def select_polygon(self):
        """使用多边形选择区域"""
        fig, ax = plt.subplots()
        ax.imshow(self.image_data, origin='lower', extent=self.extent, cmap='sdoaia94')
        ax.set_title('单击以添加多边形顶点，右键闭合多边形')
        
        polygon_coords = []
        
        def onselect(vertices):
            self.coords = vertices
            # 创建多边形掩模
            ny, nx = self.image_data.shape
            if self.extent is not None:
                xmin, xmax, ymin, ymax = self.extent
                dx = (xmax - xmin) / nx
                dy = (ymax - ymin) / ny
                x_vals = np.linspace(xmin + dx/2, xmax - dx/2, nx)
                y_vals = np.linspace(ymin + dy/2, ymax - dy/2, ny)
            else:
                x_vals = np.arange(nx)
                y_vals = np.arange(ny)
            xx, yy = np.meshgrid(x_vals, y_vals)
            from matplotlib.path import Path as mplPath
            poly_path = mplPath(vertices)
            points = np.vstack((xx.flatten(), yy.flatten())).T
            self.region_mask = poly_path.contains_points(points).reshape(xx.shape)
            self.region_type = 'polygon'
            plt.close(fig)
        
        polygon_selector = PolygonSelector(ax, onselect, useblit=True)
        plt.show()
        return self.region_mask, self.coords

def find_aia_files(data_path, wavelength, start_time, end_time):
    """
    在指定目录或通过Fido查找指定波长和时间范围的AIA文件。
    """
    data_path = Path(data_path)
    if data_path.exists():
        # 从本地目录查找
        pattern = f"*aia.lev1_euv_12s*{wavelength}*"
        files = sorted(data_path.glob(pattern))
        # 简单时间过滤（可根据需要增强）
        return [str(f) for f in files]
    else:
        # 通过Fido远程下载（需要网络）
        print(f"本地目录 {data_path} 不存在，尝试远程查询...")
        result = Fido.search(a.Time(start_time, end_time),
                             a.Instrument('AIA'),
                             a.Wavelength(wavelength * u.angstrom))
        if len(result) > 0:
            files = Fido.fetch(result[0])
            return [str(f) for f in files]
        else:
            return []

def extract_region_data(file_list, region_mask, extent=None):
    """
    从文件列表中提取区域数据。
    返回时间列表和区域统计量（平均值、最大值、总和）。
    """
    times = []
    means = []
    maxs = []
    totals = []
    
    for file_path in file_list:
        try:
            aia_map = sunpy.map.Map(file_path)
            data = aia_map.data
            # 如果提供了extent，需要确保掩模与数据形状匹配
            if region_mask is not None:
                if region_mask.shape != data.shape:
                    # 尝试调整掩模大小（简单实现，可能需要更精确的坐标转换）
                    import scipy.ndimage
                    region_mask_resized = scipy.ndimage.zoom(region_mask, 
                        (data.shape[0]/region_mask.shape[0], data.shape[1]/region_mask.shape[1]), 
                        order=0)
                    region_mask = region_mask_resized > 0.5
                region_data = data[region_mask]
            else:
                region_data = data.flatten()
            
            times.append(aia_map.date.datetime)
            means.append(np.mean(region_data))
            maxs.append(np.max(region_data))
            totals.append(np.sum(region_data))
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
            continue
    
    return times, means, maxs, totals

def plot_time_series(times, means, maxs, totals, region_type, output_dir='./output'):
    """
    绘制时间序列图并保存。
    """
    os.makedirs(output_dir, exist_ok=True)
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    
    axes[0].plot(times, means, 'b-', label='平均值')
    axes[0].set_ylabel('DN/s')
    axes[0].set_title(f'选定区域 ({region_type}) 随时间变化 - 平均值')
    axes[0].legend()
    axes[0].grid(True)
    
    axes[1].plot(times, maxs, 'r-', label='最大值')
    axes[1].set_ylabel('DN/s')
    axes[1].set_title('最大值')
    axes[1].legend()
    axes[1].grid(True)
    
    axes[2].plot(times, totals, 'g-', label='总和')
    axes[2].set_ylabel('DN/s')
    axes[2].set_xlabel('时间')
    axes[2].set_title('总和')
    axes[2].legend()
    axes[2].grid(True)
    
    plt.tight_layout()
    
    # 保存图像
    output_path = os.path.join(output_dir, f'AIA_slice_{region_type}_{times[0].strftime("%Y%m%d")}.png')
    plt.savefig(output_path, dpi=150)
    print(f"图像已保存至: {output_path}")
    
    # 保存数据到CSV
    import csv
    csv_path = os.path.join(output_dir, f'AIA_slice_{region_type}_{times[0].strftime("%Y%m%d")}.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['时间', '平均值', '最大值', '总和'])
        for t, m, mx, tot in zip(times, means, maxs, totals):
            writer.writerow([t.isoformat(), m, mx, tot])
    print(f"数据已保存至: {csv_path}")
    
    plt.show()

def main():
    """
    主函数：协调整个流程。
    """
    import argparse
    parser = argparse.ArgumentParser(description='AIA区域切片时间序列分析')
    parser.add_argument('--data_path', type=str, default='./data', 
                        help='AIA数据目录路径')
    parser.add_argument('--wavelength', type=int, default=94,
                        help='AIA波长（单位：埃）')
    parser.add_argument('--start_time', type=str, default='2025-01-01 00:00:00',
                        help='开始时间（格式：YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--end_time', type=str, default='2025-01-01 01:00:00',
                        help='结束时间（格式：YYYY-MM-DD HH:MM:SS）')
    parser.add_argument('--region_type', type=str, choices=['rectangle', 'polygon'], default='rectangle',
                        help='区域选择类型：rectangle（矩形）或 polygon（多边形）')
    parser.add_argument('--output_dir', type=str, default='./output',
                        help='输出目录')
    
    args = parser.parse_args()
    
    # 1. 查找文件
    print("正在查找AIA文件...")
    file_list = find_aia_files(args.data_path, args.wavelength, args.start_time, args.end_time)
    if not file_list:
        print("未找到符合条件的AIA文件。")
        return
    print(f"找到 {len(file_list)} 个文件。")
    
    # 2. 加载第一幅图像用于区域选择
    try:
        first_map = sunpy.map.Map(file_list[0])
        first_data = first_map.data
        # 计算图像范围（以角秒为单位）
        # 注意：这里简化处理，实际应根据WCS计算
        ny, nx = first_data.shape
        extent = [-nx/2, nx/2, -ny/2, ny/2]  # 假设中心在(0,0)，每像素1角秒
    except Exception as e:
        print(f"加载第一幅图像失败: {e}")
        return
    
    # 3. 区域选择
    print("请选择区域...")
    selector = RegionSelector(first_data, extent=extent)
    if args.region_type == 'rectangle':
        region_mask, coords = selector.select_rectangle()
    else:
        region_mask, coords = selector.select_polygon()
    
    if region_mask is None:
        print("区域选择失败或取消。")
        return
    print(f"区域选择完成，类型：{selector.region_type}，坐标：{coords}")
    
    # 4. 提取数据
    print("正在提取区域数据...")
    times, means, maxs, totals = extract_region_data(file_list, region_mask, extent)
    
    if not times:
        print("未提取到有效数据。")
        return
    
    # 5. 绘图
    print("正在生成时间序列图...")
    plot_time_series(times, means, maxs, totals, selector.region_type, args.output_dir)
    
    print("处理完成！")

if __name__ == '__main__':
    main()
