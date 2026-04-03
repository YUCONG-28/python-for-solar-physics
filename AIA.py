# -*- coding: utf-8 -*-
"""
Created on Sun Nov 23 00:19:30 2025
@author: Severus

"""

import gc
import time
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # 强制非交互式后端，多进程安全且防内存泄漏
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import astropy.units as u
from astropy.coordinates import SkyCoord
from sunpy.coordinates import propagate_with_solar_surface
import sunpy.map
from tqdm import tqdm


# ==============================================================================
# 全局配置
# ==============================================================================
AIA_CONFIG: dict = {
    94:  {'cmap': 'sdoaia94','vmin':0.4, 'vmax': 6666},
    131: {'cmap': 'sdoaia131','vmin':0.7, 'vmax': 6666},
    171: {'cmap': 'sdoaia171','vmin':16, 'vmax': 6666},
    193: {'cmap': 'sdoaia193','vmin':42, 'vmax': 6666},
    211: {'cmap': 'sdoaia211','vmin':18, 'vmax': 6666},
    304: {'cmap': 'sdoaia304','vmin':0.9, 'vmax': 2222},
    335: {'cmap': 'sdoaia335'},
}


@dataclass
class AIAConfig:
    data_path:  str           = r'D:\spike_topping_type_III\2025\20250428\AIA'
    output_dir: Optional[str] = None
    start_idx: int            = 0
    end_idx:   Optional[int]  = None
    roi_bounds: Tuple[float, float, float, float] = (-1150, 1150, -1150, 1150)
    user_vmin: Optional[float] = None
    user_vmax: Optional[float] = None
    user_cmap: Optional[str]   = None
    
    # 动态 figsize 的基础宽度（英寸），高度会自动按比例计算
    base_fig_width: float = 8.0 
    dpi:           int  = 300
    show_limb:     bool = False  # 如果开启，需将 limb 颜色改为黑色
    show_grid:     bool = True   # 默认开启以匹配参考图
    show_colorbar: bool = False
    save_image:       bool = True
    show_image:       bool = False
    use_band_subdirs: bool = True
    
    max_workers: Optional[int] = None 

    def __post_init__(self):
        if self.output_dir is None:
            self.output_dir = self.data_path


# ==============================================================================
# 内部工具函数
# ==============================================================================
def _resolve_files(input_path: Path, start_idx: int, end_idx: Optional[int]) -> list:
    if input_path.is_file():
        file_list = [input_path]
    elif input_path.is_dir():
        file_list = sorted(input_path.rglob('*.fits'))
    else:
        raise ValueError(f"无效的路径: {input_path}")

    total = len(file_list)
    if total == 0:
        raise ValueError("数据目录或其子目录中没有找到 FITS 文件！")

    end = total if end_idx is None else min(end_idx, total)
    selected = file_list[start_idx:end]
    print(f"共发现 {total} 个文件，已选择处理 {len(selected)} 个（索引: {start_idx} ~ {end - 1}）")
    return selected


def _parse_timestr(file_path: Path) -> str:
    """精准提取格式类似于 2025-01-24T033001Z 的时间字符串"""
    # 尝试正则匹配标准的 ISO 时间格式
    match = re.search(r'\d{4}-\d{2}-\d{2}T\d{6}Z', file_path.name)
    if match:
        return match.group(0)
    
    # 备选方案
    parts = file_path.name.split('.')
    for part in parts:
        if 'T' in part and 'Z' in part:
            return part
    return file_path.stem


def _resolve_display_params(
    current_map: sunpy.map.GenericMap,
    user_cmap:   Optional[str],
    user_vmin:   Optional[float],
    user_vmax:   Optional[float],
) -> Tuple[str, mcolors.Normalize]:
    wave_val = int(current_map.wavelength.value)
    config = AIA_CONFIG.get(wave_val, {})
    sunpy_norm = current_map.plot_settings['norm']
    sunpy_cmap = current_map.plot_settings['cmap']

    final_cmap = user_cmap or config.get('cmap', sunpy_cmap)
    final_vmin = user_vmin if user_vmin is not None else config.get('vmin', sunpy_norm.vmin)
    final_vmax = user_vmax if user_vmax is not None else config.get('vmax', sunpy_norm.vmax)

    if not (final_vmin and final_vmax and final_vmin > 0 and final_vmax > final_vmin):
        final_vmin, final_vmax = 1.0, 1e4

    return final_cmap, mcolors.LogNorm(vmin=final_vmin, vmax=final_vmax)


# ==============================================================================
# 单文件处理核心函数
# ==============================================================================
def _process_single_worker(file_path: Path, cfg: AIAConfig) -> Tuple[bool, str]:
    current_map = None
    raw_cutout = None
    cutout_map = None
    fig = None
    
    try:
        current_map = sunpy.map.Map(file_path)
        wave_val = int(current_map.wavelength.value)
        exp_time = current_map.exposure_time.to_value(u.s)
        
        if exp_time <= 0:
            return False, f"{file_path.name}: 曝光时间异常 ({exp_time}s)"

        # 1. 坐标与裁剪边界解析
        tx1, tx2, ty1, ty2 = cfg.roi_bounds
        roi_bl_tx, roi_bl_ty = tx1 * u.arcsec, ty1 * u.arcsec
        roi_tr_tx, roi_tr_ty = tx2 * u.arcsec, ty2 * u.arcsec

        # 2. 计算自适应 figsize (高度根据物理比例计算)
        dx = abs(tx2 - tx1)
        dy = abs(ty2 - ty1)
        aspect_ratio = dy / dx if dx != 0 else 1.0
        fig_width = cfg.base_fig_width
        fig_height = fig_width * aspect_ratio

        # 3. 裁剪处理
        with propagate_with_solar_surface():
            frame = current_map.coordinate_frame
            bl = SkyCoord(Tx=roi_bl_tx, Ty=roi_bl_ty, frame=frame)
            tr = SkyCoord(Tx=roi_tr_tx, Ty=roi_tr_ty, frame=frame)
            raw_cutout = current_map.submap(bl, top_right=tr)

        normalized_data = raw_cutout.data / exp_time
        cutout_map = sunpy.map.Map(normalized_data, raw_cutout.meta)

        final_cmap, final_norm = _resolve_display_params(
            current_map, cfg.user_cmap, cfg.user_vmin, cfg.user_vmax
        )
        time_str = _parse_timestr(file_path)

        # 4. 画图设置 (核心修改：设置背景为白色)
        # 显式设置 figure 的 facecolor 为白色
        fig = plt.figure(figsize=(fig_width, fig_height), facecolor='white')
        ax = fig.add_subplot(projection=cutout_map)
        # 设置 axes 的 facecolor（绘图区域内部）为白色
        ax.set_facecolor('white')

        im = cutout_map.plot(axes=ax, cmap=final_cmap, norm=final_norm, annotate=False)

        if cfg.show_limb:
            # 白色背景下，Limb 颜色改为黑色
            current_map.draw_limb(axes=ax, color='black', linewidth=0.8, alpha=0.6)

        if cfg.show_grid:
            # 核心修改：为了在白色背景下可见，网格线颜色改为黑色
            cutout_map.draw_grid(axes=ax, color='black', linewidth=0.3, alpha=0.3, linestyle='--')

        if cfg.show_colorbar:
            cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Intensity (DN/s)', fontsize=10)
            cbar.ax.tick_params(labelsize=9)

        # 5. UI 细节精调 (匹配参考图布局)
        lon, lat = ax.coords
        lon.set_axislabel('Helioprojective Longitude (Solar-X)', fontsize=10)
        lat.set_axislabel('Helioprojective Latitude (Solar-Y)', fontsize=10)
        
        # 刻度线和标签（默认已经是黑色，在白色背景下清晰）
        
        # 刻度线向内，且四面均显示
        lon.set_ticks(direction='in')
        lat.set_ticks(direction='in')
        lon.set_ticks_position('tb')
        lat.set_ticks_position('lr')

        # 设置标题仅为时间
        ax.set_title(f"{time_str}", fontsize=12, pad=8)

        # 6. 保存图片 (文件名直接用时间)
        if cfg.save_image and cfg.output_dir:
            save_dir = Path(cfg.output_dir) / str(wave_val) if cfg.use_band_subdirs else Path(cfg.output_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            # 输出名字：时间字符串.png (如果你需要jpg，这里改成.jpg即可)
            save_path = save_dir / f"{time_str}.png"
            # 核心修改：保存时设置 facecolor='white'
            fig.savefig(save_path, dpi=cfg.dpi, bbox_inches='tight', facecolor='white', pad_inches=0.1)
        
        return True, ""

    except Exception as e:
        return False, f"{file_path.name} -> {str(e)}"

    finally:
        if fig is not None:
            plt.close(fig)
        del current_map, raw_cutout, cutout_map
        gc.collect()


# ==============================================================================
# 批量执行入口
# ==============================================================================
def process_aia_fits(cfg: AIAConfig):
    input_path = Path(cfg.data_path)
    selected_files = _resolve_files(input_path, cfg.start_idx, cfg.end_idx)

    start_time = time.time()
    success_cnt = 0
    error_cnt = 0

    workers = cfg.max_workers or max(1, multiprocessing.cpu_count() - 1)
    print(f"启动多进程处理，分配核心数: {workers} ...")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_single_worker, f, cfg): f for f in selected_files}
        
        for future in tqdm(as_completed(futures), total=len(selected_files), desc="Processing", unit="file"):
            success, msg = future.result()
            if success:
                success_cnt += 1
            else:
                error_cnt += 1
                tqdm.write(f"\n  [失败] {msg}")

    elapsed = time.time() - start_time
    print(f"\n处理完成！成功: {success_cnt}，失败: {error_cnt}，总耗时 {elapsed:.2f} 秒")


if __name__ == "__main__":
    # 使用白色背景和黑色网格
    cfg = AIAConfig(show_image=False, show_grid=True)  
    print("--- 开始极速批量处理 AIA 数据 (白色背景版) ---")
    process_aia_fits(cfg)