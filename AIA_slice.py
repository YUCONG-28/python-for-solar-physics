# -*- coding: utf-8 -*-
"""
AIA区域切片时间序列分析
优化版本：支持参数配置和直接指定文件
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector, PolygonSelector
import sunpy.map
from sunpy.net import Fido, attrs as a
import astropy.units as u
import os
from pathlib import Path
import warnings
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import argparse
import csv
from datetime import datetime
import sys

warnings.filterwarnings('ignore')

@dataclass
class AIASliceConfig:
    """AIA切片分析配置参数"""
    # 输入选项
    input_dir: str = "./data"
    file_pattern: str = "*aia.lev1_euv_12s*"
    wavelength: Optional[int] = None  # 单位：埃，如果为None则匹配所有波长
    use_fido: bool = False  # 是否使用Fido远程下载
    
    # 时间范围
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    
    # 区域选择
    region_type: str = "rectangle"  # rectangle, polygon, manual
    manual_coords: Optional[Tuple] = None  # 手动指定坐标
    
    # 数据处理
    statistics: List[str] = field(default_factory=lambda: ["mean", "max", "sum"])
    normalize: bool = False  # 是否归一化数据
    
    # 输出选项
    output_dir: str = "./output"
    save_csv: bool = True
    save_plot: bool = True
    plot_dpi: int = 150
    show_plot: bool = True
    
    # 显示选项
    cmap: str = "sdoaia94"
    figsize: Tuple[int, int] = (12, 10)

class RegionSelector:
    """
    交互式区域选择工具，支持矩形和多边形选择。
    """
    def __init__(self, image_data, extent=None, cmap="sdoaia94"):
        self.image_data = image_data
        self.extent = extent
        self.cmap = cmap
        self.region_mask = None
        self.region_type = None
        self.coords = None
        
    def select_rectangle(self):
        """使用矩形选择区域"""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(self.image_data, origin='lower', extent=self.extent, cmap=self.cmap)
        ax.set_title('单击并拖动以选择矩形区域')
        ax.set_xlabel('X (arcsec)')
        ax.set_ylabel('Y (arcsec)')
        
        def onselect(eclick, erelease):
            x1, y1 = eclick.xdata, eclick.ydata
            x2, y2 = erelease.xdata, erelease.ydata
            self.coords = (min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2))
            
            # 创建矩形掩模
            ny, nx = self.image_data.shape
            if self.extent is not None:
                xmin, xmax, ymin, ymax = self.extent
                x_vals = np.linspace(xmin, xmax, nx)
                y_vals = np.linspace(ymin, ymax, ny)
            else:
                x_vals = np.arange(nx)
                y_vals = np.arange(ny)
                
            xx, yy = np.meshgrid(x_vals, y_vals)
            self.region_mask = (xx >= self.coords[0]) & (xx <= self.coords[1]) & \
                               (yy >= self.coords[2]) & (yy <= self.coords[3])
            self.region_type = 'rectangle'
            
            # 显示选择区域
            rect = plt.Rectangle((self.coords[0], self.coords[2]),
                                 self.coords[1] - self.coords[0],
                                 self.coords[3] - self.coords[2],
                                 fill=False, edgecolor='red', linewidth=2)
            ax.add_patch(rect)
            plt.draw()
            plt.pause(0.5)
            plt.close(fig)
        
        rect_selector = RectangleSelector(ax, onselect, useblit=True,
                                          button=[1], minspanx=5, minspany=5,
                                          spancoords='data', interactive=True)
        plt.show()
        return self.region_mask, self.coords
    
    def select_polygon(self):
        """使用多边形选择区域"""
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.imshow(self.image_data, origin='lower', extent=self.extent, cmap=self.cmap)
        ax.set_title('单击以添加多边形顶点，右键闭合多边形')
        ax.set_xlabel('X (arcsec)')
        ax.set_ylabel('Y (arcsec)')
        
        def onselect(vertices):
            self.coords = vertices
            
            # 创建多边形掩模
            ny, nx = self.image_data.shape
            if self.extent is not None:
                xmin, xmax, ymin, ymax = self.extent
                x_vals = np.linspace(xmin, xmax, nx)
                y_vals = np.linspace(ymin, ymax, ny)
            else:
                x_vals = np.arange(nx)
                y_vals = np.arange(ny)
                
            xx, yy = np.meshgrid(x_vals, y_vals)
            from matplotlib.path import Path as mplPath
            poly_path = mplPath(vertices)
            points = np.vstack((xx.flatten(), yy.flatten())).T
            self.region_mask = poly_path.contains_points(points).reshape(xx.shape)
            self.region_type = 'polygon'
            
            # 显示选择区域
            from matplotlib.patches import Polygon
            poly_patch = Polygon(vertices, fill=False, edgecolor='red', linewidth=2)
            ax.add_patch(poly_patch)
            plt.draw()
            plt.pause(0.5)
            plt.close(fig)
        
        polygon_selector = PolygonSelector(ax, onselect, useblit=True)
        plt.show()
        return self.region_mask, self.coords

class AIASliceProcessor:
    """AIA切片处理器"""
    
    def __init__(self, config: AIASliceConfig):
        self.config = config
        self.file_list = []
        self.region_mask = None
        self.results = {}
        
    def find_aia_files(self) -> List[str]:
        """查找AIA文件"""
        if self.config.use_fido and self.config.start_time and self.config.end_time:
            return self._find_via_fido()
        else:
            return self._find_local_files()
    
    def _find_local_files(self) -> List[str]:
        """查找本地文件"""
        data_path = Path(self.config.input_dir)
        if not data_path.exists():
            print(f"警告：目录 {self.config.input_dir} 不存在")
            return []
        
        # 构建文件匹配模式
        pattern = self.config.file_pattern
        if self.config.wavelength:
            pattern = f"*{self.config.wavelength}*"
        
        # 查找文件
        files = sorted(data_path.glob(pattern))
        if not files:
            # 尝试其他常见模式
            patterns = [
                f"*aia*{self.config.wavelength}*.fits",
                f"*AIA*{self.config.wavelength}*.fits",
                f"*{self.config.wavelength}*.fits"
            ]
            for pat in patterns:
                files = sorted(data_path.glob(pat))
                if files:
                    break
        
        return [str(f) for f in files]
    
    def _find_via_fido(self) -> List[str]:
        """通过Fido远程下载"""
        print("正在通过Fido远程查询AIA数据...")
        try:
            result = Fido.search(a.Time(self.config.start_time, self.config.end_time),
                                 a.Instrument('AIA'),
                                 a.Wavelength(self.config.wavelength * u.angstrom))
            if len(result) > 0:
                files = Fido.fetch(result[0])
                return [str(f) for f in files]
        except Exception as e:
            print(f"Fido查询失败: {e}")
        return []
    
    def select_region(self, aia_map: sunpy.map.Map) -> np.ndarray:
        """选择区域"""
        data = aia_map.data
        
        # 计算实际范围（使用WCS信息）
        try:
            # 尝试从地图获取实际坐标范围
            coord_top_left = aia_map.pixel_to_world(0*u.pix, 0*u.pix)
            coord_bottom_right = aia_map.pixel_to_world(
                (aia_map.data.shape[1]-1)*u.pix, 
                (aia_map.data.shape[0]-1)*u.pix
            )
            extent = [
                coord_top_left.Tx.value,
                coord_bottom_right.Tx.value,
                coord_bottom_right.Ty.value,
                coord_top_left.Ty.value
            ]
        except:
            # 简化处理
            ny, nx = data.shape
            extent = [-nx/2, nx/2, -ny/2, ny/2]
        
        selector = RegionSelector(data, extent=extent, cmap=self.config.cmap)
        
        if self.config.region_type == "rectangle":
            region_mask, coords = selector.select_rectangle()
        elif self.config.region_type == "polygon":
            region_mask, coords = selector.select_polygon()
        else:
            raise ValueError(f"不支持的区域类型: {self.config.region_type}")
        
        print(f"区域选择完成: {selector.region_type}, 坐标: {coords}")
        return region_mask
    
    def extract_data(self, file_list: List[str], region_mask: np.ndarray) -> Dict[str, Any]:
        """提取区域数据"""
        times = []
        stats = {stat: [] for stat in self.config.statistics}
        
        for i, file_path in enumerate(file_list):
            try:
                print(f"处理文件 {i+1}/{len(file_list)}: {Path(file_path).name}")
                aia_map = sunpy.map.Map(file_path)
                data = aia_map.data
                
                # 确保掩模形状匹配
                if region_mask.shape != data.shape:
                    # 调整掩模大小
                    import scipy.ndimage
                    zoom_factors = (
                        data.shape[0] / region_mask.shape[0],
                        data.shape[1] / region_mask.shape[1]
                    )
                    region_mask_resized = scipy.ndimage.zoom(region_mask, zoom_factors, order=0)
                    region_mask_resized = region_mask_resized > 0.5
                    region_data = data[region_mask_resized]
                else:
                    region_data = data[region_mask]
                
                # 计算统计量
                times.append(aia_map.date.datetime)
                
                if "mean" in self.config.statistics:
                    stats["mean"].append(np.mean(region_data))
                if "max" in self.config.statistics:
                    stats["max"].append(np.max(region_data))
                if "sum" in self.config.statistics:
                    stats["sum"].append(np.sum(region_data))
                if "median" in self.config.statistics:
                    stats["median"].append(np.median(region_data))
                if "std" in self.config.statistics:
                    stats["std"].append(np.std(region_data))
                    
            except Exception as e:
                print(f"处理文件 {file_path} 时出错: {e}")
                continue
        
        return {"times": times, "stats": stats}
    
    def plot_results(self, results: Dict[str, Any], region_type: str):
        """绘制结果"""
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        times = results["times"]
        stats = results["stats"]
        
        n_stats = len(self.config.statistics)
        fig, axes = plt.subplots(n_stats, 1, figsize=self.config.figsize, sharex=True)
        if n_stats == 1:
            axes = [axes]
        
        colors = plt.cm.tab10(np.linspace(0, 1, n_stats))
        
        for idx, stat_name in enumerate(self.config.statistics):
            if stat_name in stats and stats[stat_name]:
                axes[idx].plot(times, stats[stat_name], '-', color=colors[idx], label=stat_name)
                axes[idx].set_ylabel('DN/s')
                axes[idx].set_title(f'选定区域 ({region_type}) - {stat_name}')
                axes[idx].legend()
                axes[idx].grid(True)
        
        axes[-1].set_xlabel('时间')
        plt.tight_layout()
        
        # 保存图像
        if self.config.save_plot:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                self.config.output_dir, 
                f'AIA_slice_{region_type}_{timestamp}.png'
            )
            plt.savefig(output_path, dpi=self.config.plot_dpi)
            print(f"图像已保存至: {output_path}")
        
        # 保存数据
        if self.config.save_csv:
            self.save_to_csv(results, region_type)
        
        if self.config.show_plot:
            plt.show()
        else:
            plt.close()
    
    def save_to_csv(self, results: Dict[str, Any], region_type: str):
        """保存数据到CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(
            self.config.output_dir, 
            f'AIA_slice_{region_type}_{timestamp}.csv'
        )
        
        times = results["times"]
        stats = results["stats"]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            header = ['时间'] + self.config.statistics
            writer.writerow(header)
            
            for i, t in enumerate(times):
                row = [t.isoformat()]
                for stat in self.config.statistics:
                    if i < len(stats[stat]):
                        row.append(stats[stat][i])
                    else:
                        row.append(np.nan)
                writer.writerow(row)
        
        print(f"数据已保存至: {csv_path}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='AIA区域切片时间序列分析')
    
    # 输入选项
    parser.add_argument('--input_dir', type=str, default='./data',
                        help='AIA数据目录路径')
    parser.add_argument('--file_pattern', type=str, default='*aia.lev1_euv_12s*',
                        help='文件匹配模式')
    parser.add_argument('--wavelength', type=int, default=None,
                        help='AIA波长（单位：埃），如果未指定则匹配所有波长')
    
    # 区域选择
    parser.add_argument('--region_type', type=str, choices=['rectangle', 'polygon'], 
                        default='rectangle',
                        help='区域选择类型：rectangle（矩形）或 polygon（多边形）')
    
    # 输出选项
    parser.add_argument('--output_dir', type=str, default='./output',
                        help='输出目录')
    parser.add_argument('--statistics', type=str, nargs='+', 
                        default=['mean', 'max', 'sum'],
                        help='统计量列表，可选：mean, max, sum, median, std')
    
    # 其他选项
    parser.add_argument('--no_plot', action='store_true',
                        help='不显示图形界面')
    parser.add_argument('--no_csv', action='store_true',
                        help='不保存CSV文件')
    
    args = parser.parse_args()
    
    # 创建配置
    config = AIASliceConfig(
        input_dir=args.input_dir,
        file_pattern=args.file_pattern,
        wavelength=args.wavelength,
        region_type=args.region_type,
        output_dir=args.output_dir,
        statistics=args.statistics,
        show_plot=not args.no_plot,
        save_csv=not args.no_csv
    )
    
    # 创建处理器
    processor = AIASliceProcessor(config)
    
    # 查找文件
    print("正在查找AIA文件...")
    file_list = processor.find_aia_files()
    if not file_list:
        print("未找到符合条件的AIA文件。")
        sys.exit(1)
    print(f"找到 {len(file_list)} 个文件。")
    
    # 加载第一幅图像用于区域选择
    try:
        first_map = sunpy.map.Map(file_list[0])
        print(f"使用文件进行区域选择: {Path(file_list[0]).name}")
    except Exception as e:
        print(f"加载第一幅图像失败: {e}")
        sys.exit(1)
    
    # 选择区域
    print("请选择区域...")
    region_mask = processor.select_region(first_map)
    if region_mask is None:
        print("区域选择失败或取消。")
        sys.exit(1)
    
    # 提取数据
    print("正在提取区域数据...")
    results = processor.extract_data(file_list, region_mask)
    
    if not results["times"]:
        print("未提取到有效数据。")
        sys.exit(1)
    
    # 绘制结果
    print("正在生成时间序列图...")
    processor.plot_results(results, config.region_type)
    
    print("处理完成！")

if __name__ == '__main__':
    main()
