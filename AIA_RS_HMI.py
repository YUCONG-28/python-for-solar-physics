# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 22:57:26 2026

@author: Severus

"""

import matplotlib
matplotlib.use('Agg')   # ★ 优化5：非交互后端，子进程安全，节省内存

import os
import gc
import re
import time
import glob
import psutil
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Ellipse
from matplotlib.lines import Line2D
from astropy.io import fits
from astropy.wcs import WCS
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.convolution import convolve, Gaussian2DKernel
import sunpy.map
import sunpy.coordinates
from sunpy.coordinates import frames
from scipy.ndimage import gaussian_filter
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from functools import lru_cache, partial
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings('ignore')

plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# ============================================================
#  模块级预编译正则
# ============================================================
_RE_MHZ         = re.compile(r'(\d+\.?\d*)\s*MHz', re.IGNORECASE)
_RE_AIA_PATS    = [
    re.compile(r'aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)'),
    re.compile(r'aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)'),
    re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'),
    re.compile(r'(\d{4}-\d{2}-\d{2}T\d{6})'),
]
_RE_HMI_PAT     = re.compile(r'(\d{8})_(\d{6})')
_RE_BAND_SORTED = re.compile(r'(\d+\.?\d*)MHz')
# 扩展时间格式常量
_DATETIME_FMTS  = [
    # 标准ISO格式
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H%M%S.%f", "%Y-%m-%dT%H%M%S",
    # 带时区信息
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H%M%S.%fZ", "%Y-%m-%dT%H%M%SZ",
    # 空格分隔
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H%M%S.%f", "%Y-%m-%d %H%M%S",
    # 简写格式
    "%Y%m%dT%H%M%S.%f", "%Y%m%dT%H%M%S", "%Y%m%d%H%M%S.%f", "%Y%m%d%H%M%S",
    # HMI格式
    "%Y%m%d_%H%M%S",
    # 其他常见格式
    "%d/%m/%YT%H:%M:%S.%f", "%d/%m/%YT%H:%M:%S", "%d-%b-%YT%H:%M:%S.%f", "%d-%b-%YT%H:%M:%S"
]

# ============================================================
#  配置类简化
# ============================================================
@dataclass
class Config:
    radio_base_dir: str = r'<PROJECT_ROOT>\2025\20250124\RS_0447-0450'
    aia_base_dir:   str = r'<PROJECT_ROOT>\2025\20250124\AIA\171\1'
    hmi_base_dir:   str = r'<PROJECT_ROOT>\2025\20250124\AIA\hmi\1'
    output_dir:     str = r'<PROJECT_ROOT>\2025\20250124\AIA_RS_HMI\LL'

    save_figure:        bool          = True
    dpi:                int           = 300
    aia_file_start_idx: int           = 392
    aia_file_end_idx:   Optional[int] = 397

    selected_bands:      List[str]    = field(default_factory=lambda: [
        '149MHz', '164MHz', '190MHz', '223MHz', '238MHz', '300MHz', '309MHz', '324MHz'])
    polarization_mode:   str          = 'LL'
    radio_time_threshold: int         = 6
    max_radio_per_band:  int          = 28

    normalization_mode:  str          = 'peak'          # 'peak' 或 'rms'
    contour_levels_peak: List[float]  = field(default_factory=lambda: [0.95])
    rms_sigma_levels:    List[float]  = field(default_factory=lambda: [5.0, 15.0, 30.0])
    rms_box_fraction:    float        = 0.15

    contour_linewidths:  List[float]  = field(default_factory=lambda: [2.0])
    contour_alpha:       float        = 0.90
    contour_smooth_sigma: float       = 0   # 展示级平滑 sigma（像素），0 = 关闭

    show_beam:           bool         = True
    beam_inset_fraction: float        = 0.12

    overlay_hmi:          bool        = True
    hmi_time_threshold:   int         = 24
    hmi_threshold_gauss:  float       = 0.0
    hmi_sigma:            int         = 2
    hmi_levels_gauss:     List[float] = field(default_factory=lambda: [100.0])

    aia_vmin:        float       = 16
    aia_vmax:        float       = 6666
    aia_cmap:        str         = 'sdoaia171'
    roi_bottom_left: List[float] = field(default_factory=lambda: [300, -800])
    roi_top_right:   List[float] = field(default_factory=lambda: [1500, 300])

    band_colors_dict: dict = field(default_factory=lambda: {
        '149.0MHz': ('cyan',    'deepskyblue'),
        '164.0MHz': ('lime',    'green'),
        '190.0MHz': ('magenta', 'darkviolet'),
        '205.0MHz': ('yellow',  'orange'),
        '223.0MHz': ('red',     'darkred'),
        '238.0MHz': ('white',   'lightgray'),
    })
    default_colors: List[Tuple] = field(default_factory=lambda: [
        ('yellow', 'orange'), ('red', 'darkred'), ('white', 'lightgray'),
        ('pink', 'hotpink'), ('skyblue', 'deepskyblue'), ('violet', 'darkviolet'),
    ])

    # 简化选项
    num_workers:         int   = 8
    memory_limit_pct:    float = 85.0
    radio_use_float32:   bool  = True
    
    # 简化：移除通量归一化和复杂验证
    apply_background_subtraction: bool = False  # 简化：默认不应用背景扣除
    debug_mode: bool = True  # 改为True以显示详细匹配信息
    
    # 简化重投影选项
    coordinate_search_radius: float = 1.0  # 坐标查找搜索半径（度）
    quick_test: bool = False
    test_file_limit: int = 5  # 快速测试时的文件数量限制

# ============================================================
#  颜色缓存
# ============================================================
def _build_band_color_cache(cfg: Config) -> List[Tuple[float, Tuple]]:
    """将 band_colors_dict 解析为 [(mhz_float, (main, dark)), ...]，仅需调用一次。"""
    cache = []
    for key, val in cfg.band_colors_dict.items():
        m = _RE_MHZ.search(key)
        if m:
            cache.append((float(m.group(1)), val))
    return cache

# ============================================================
#  Gaussian 核缓存
# ============================================================
@lru_cache(maxsize=16)
def _make_gaussian_kernel(sigma: float) -> Gaussian2DKernel:
    """相同 sigma 只创建一次 Gaussian2DKernel 对象。"""
    return Gaussian2DKernel(x_stddev=sigma)

# ============================================================
#  内存监控
# ============================================================
def check_memory_usage(limit: float = 90.0):
    """检查内存占用，超过阈值则执行垃圾回收并等待释放。"""
    mem_percent = psutil.virtual_memory().percent
    if mem_percent >= limit:
        print(f"\n[警告] 内存占用已达 {mem_percent}% (阈值: {limit}%)，正在执行深度清理并挂起...")
        while psutil.virtual_memory().percent >= limit:
            gc.collect()
            time.sleep(1.0)
        print(f"[恢复] 内存占用已降至 {psutil.virtual_memory().percent}%，恢复执行。")

# ============================================================
#  时间解析
# ============================================================
def parse_aia_time_from_filename(filename: str) -> Optional[datetime]:
    """从 AIA 文件名中提取观测时间（支持多种命名模式）。"""
    basename = os.path.basename(filename)
    
    # 尝试从FITS头直接读取（如果文件可访问）
    try:
        if os.path.exists(filename):
            header = fits.getheader(filename, 0)
            date_obs = str(header.get('DATE-OBS', '')).strip()
            if date_obs:
                for fmt in _DATETIME_FMTS:
                    try:
                        # 清理时间字符串
                        date_obs_clean = date_obs.replace('Z', '').replace('T', ' ').strip()
                        return datetime.strptime(date_obs_clean, fmt)
                    except ValueError:
                        continue
    except Exception:
        pass
    
    # 从文件名解析（备用方法）
    for pat in _RE_AIA_PATS:
        m = pat.search(basename)
        if m:
            ts = m.group(1).replace('Z', '').replace('T', ' ')
            # 标准化时间格式
            if ':' not in ts and len(ts) >= 14:
                # 格式如 20240124T120000
                ts = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:]}"
            
            for fmt in _DATETIME_FMTS:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
    
    return None

def parse_hmi_time_from_filename(filename: str) -> Optional[datetime]:
    """从 HMI 文件名中提取观测时间（格式如 YYYYMMDD_HHMMSS）。"""
    m = _RE_HMI_PAT.search(filename)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return None

# ============================================================
#  简化射电数据工具
# ============================================================
def extract_radio_2d_data(fits_path: str, use_float32: bool = True, cfg: Optional[Config] = None) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], fits.Header, Optional[WCS]]:
    """
    简化版：只提取射电数据和坐标图
    """
    try:
        with fits.open(fits_path) as hdu_data:
            data = hdu_data[0].data
            # 简化维度压缩逻辑
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            header = hdu_data[0].header.copy()
            
            # 获取基目录和文件名
            base_dir = os.path.dirname(fits_path)
            base_name = os.path.basename(fits_path)
            
            # 提取频率
            freq_match = re.search(r'(\d+)MHz', base_name, re.IGNORECASE)
            if freq_match:
                freq_prefix = freq_match.group(0)  # 如 "149MHz"
            else:
                # 使用目录名作为频率
                parent_dir = os.path.dirname(base_dir)
                freq_prefix = os.path.basename(parent_dir)
            
            ra_map = None
            dec_map = None
            
            # 简化：只查找坐标图文件
            if freq_prefix:
                # 在当前目录和父目录查找坐标图文件
                search_dirs = [base_dir, os.path.dirname(base_dir)]
                
                for search_dir in search_dirs:
                    if os.path.isdir(search_dir):
                        for file in os.listdir(search_dir):
                            if freq_prefix in file:
                                file_path = os.path.join(search_dir, file)
                                try:
                                    if 'RightAscension' in file or 'RA' in file:
                                        with fits.open(file_path) as hdu_ra:
                                            ra_map = hdu_ra[0].data
                                            while ra_map.ndim > 2:
                                                ra_map = ra_map[0]
                                            ra_map = np.squeeze(ra_map)
                                            if use_float32:
                                                ra_map = ra_map.astype(np.float32)
                                    elif 'Declination' in file or 'Dec' in file:
                                        with fits.open(file_path) as hdu_dec:
                                            dec_map = hdu_dec[0].data
                                            while dec_map.ndim > 2:
                                                dec_map = dec_map[0]
                                            dec_map = np.squeeze(dec_map)
                                            if use_float32:
                                                dec_map = dec_map.astype(np.float32)
                                except Exception:
                                    pass
            
            # 简化：不构建WCS，只使用坐标图
            dtype = np.float32 if use_float32 else np.float64
            return data.astype(dtype), ra_map, dec_map, header, None
            
    except Exception as e:
        print(f"读取FITS文件失败 {fits_path}: {e}")
        return None, None, None, None, None

def estimate_rms_noise(data: np.ndarray, box_fraction: float = 0.15) -> float:
    """通过图像四个角部区域估算背景噪声 RMS（用于 rms 模式等值线）。"""
    ny, nx = data.shape
    bx = max(int(nx * box_fraction), 5)
    by = max(int(ny * box_fraction), 5)
    
    # 提取四个角区域
    corners = [
        data[:by, :bx], data[:by, -bx:],
        data[-by:, :bx], data[-by:, -bx:]
    ]
    
    # 合并角部像素
    corner_pixels = np.concatenate([c.ravel() for c in corners])
    corner_pixels = corner_pixels[~np.isnan(corner_pixels)]
    
    if len(corner_pixels) < 10:
        # 如果角部像素不足，使用边缘像素
        edges = np.concatenate([
            data[:by, :].ravel(), data[-by:, :].ravel(),
            data[:, :bx].ravel(), data[:, -bx:].ravel()
        ])
        edge_pixels = edges[~np.isnan(edges)]
        if len(edge_pixels) > 0:
            corner_pixels = edge_pixels
    
    if len(corner_pixels) == 0:
        return float(np.nanstd(data) * 0.1)
    
    # 使用中值绝对偏差（MAD）进行鲁棒估计
    median = np.median(corner_pixels)
    mad = np.median(np.abs(corner_pixels - median))
    std_est = mad * 1.4826  # 转换为标准差
    
    # 3-sigma裁剪去除异常值
    filtered = corner_pixels[np.abs(corner_pixels - median) < 3 * std_est]
    
    if len(filtered) > 0:
        return float(np.std(filtered))
    else:
        return float(std_est)

def compute_contour_levels(data: np.ndarray, cfg: Config) -> List[float]:
    """支持 normalization_mode='peak'（默认）和 'rms' 两种模式。"""
    finite_data = data[np.isfinite(data)]
    if len(finite_data) == 0:
        return []

    # 应用背景扣除（如果启用）
    if cfg.apply_background_subtraction:
        if cfg.background_estimation_method == 'median':
            background = np.median(finite_data)
        elif cfg.background_estimation_method == 'minimum':
            background = np.percentile(finite_data, 5)
        else:  # 'corner'
            background = estimate_rms_noise(data, cfg.rms_box_fraction)
        data = data - background

    if cfg.normalization_mode == 'rms':
        rms = estimate_rms_noise(data, cfg.rms_box_fraction)
        if rms <= 0:
            return []
        peak   = float(np.nanmax(finite_data))
        levels = [s * rms for s in cfg.rms_sigma_levels if 0 < s * rms < peak]
    else:
        peak   = float(np.nanmax(finite_data))
        levels = [f * peak for f in cfg.contour_levels_peak]

    return levels if levels else []

# ============================================================
#  简化重投影函数
# ============================================================
def reproject_radio_with_coordinate_lookup(radio_data: np.ndarray,
                                           ra_map: np.ndarray,
                                           dec_map: np.ndarray,
                                           target_shape: Tuple[int, int],
                                           aia_wcs_2d: WCS,
                                           cfg: Config,
                                           radio_header: Optional[fits.Header] = None) -> Optional[np.ndarray]:
    """
    简化版：只使用坐标图进行重投影，移除太阳自转修正和高度计算
    """
    try:
        if ra_map is None or dec_map is None:
            return None
        
        # 验证坐标图形状
        if ra_map.shape != radio_data.shape or dec_map.shape != radio_data.shape:
            return None

        # 使用副本
        ra_map = ra_map.copy().astype(np.float64)
        dec_map = dec_map.copy().astype(np.float64)

        # 检查坐标值范围
        ra_min, ra_max = np.nanmin(ra_map), np.nanmax(ra_map)
        dec_min, dec_max = np.nanmin(dec_map), np.nanmax(dec_map)
        
        # 检测坐标单位并转换
        if abs(ra_max) < 4.0 and abs(ra_min) < 4.0 and abs(dec_max) < 4.0 and abs(dec_min) < 4.0:
            # 弧度单位转换为度
            ra_map = np.rad2deg(ra_map)
            dec_map = np.rad2deg(dec_map)
        
        # 加上相位中心得到绝对坐标
        if radio_header is not None:
            crval1 = float(radio_header.get('CRVAL1', 0.0))
            crval2 = float(radio_header.get('CRVAL2', 0.0))
            ra_map = ra_map + crval1
            dec_map = dec_map + crval2
        
        # 标准化赤经到0-360度
        ra_map = np.mod(ra_map, 360)
        
        # 检查有效数据点
        ra_valid = np.isfinite(ra_map)
        dec_valid = np.isfinite(dec_map)
        data_valid = np.isfinite(radio_data)
        valid_mask = ra_valid & dec_valid & data_valid
        
        valid_count = np.sum(valid_mask)
        if valid_count < 100:
            return None
        
        # 提取有效点的坐标和数据
        valid_ra = ra_map[valid_mask]
        valid_dec = dec_map[valid_mask]
        valid_data = radio_data[valid_mask]
        
        # 创建目标网格
        ny, nx = target_shape
        y_target, x_target = np.mgrid[0:ny, 0:nx]
        
        # 将目标像素转换为世界坐标
        try:
            target_coords = aia_wcs_2d.pixel_to_world(x_target, y_target)
            target_eq_coords = target_coords.transform_to('icrs')
            target_ra = target_eq_coords.ra.deg.reshape(ny, nx)
            target_dec = target_eq_coords.dec.deg.reshape(ny, nx)
        except Exception:
            return None
        
        # 使用KD树进行最近邻插值
        from scipy.spatial import cKDTree
        
        # 为有效点构建KD树
        max_points = min(10000, len(valid_ra))
        if len(valid_ra) > max_points:
            indices = np.random.choice(len(valid_ra), max_points, replace=False)
            valid_ra_sampled = valid_ra[indices]
            valid_dec_sampled = valid_dec[indices]
            valid_data_sampled = valid_data[indices]
        else:
            valid_ra_sampled = valid_ra
            valid_dec_sampled = valid_dec
            valid_data_sampled = valid_data
        
        # 确保KD树的数据点都是有限的
        kdtree_valid = np.isfinite(valid_ra_sampled) & np.isfinite(valid_dec_sampled)
        valid_ra_sampled = valid_ra_sampled[kdtree_valid]
        valid_dec_sampled = valid_dec_sampled[kdtree_valid]
        valid_data_sampled = valid_data_sampled[kdtree_valid]
        
        if len(valid_ra_sampled) == 0:
            return None
        
        tree = cKDTree(np.column_stack([valid_ra_sampled, valid_dec_sampled]))
        
        # 分块处理目标网格
        chunk_size = 64
        reprojected = np.full((ny, nx), np.nan, dtype=np.float32)
        
        for i in range(0, nx, chunk_size):
            for j in range(0, ny, chunk_size):
                i_end = min(i + chunk_size, nx)
                j_end = min(j + chunk_size, ny)
                
                chunk_target_ra = target_ra[j:j_end, i:i_end]
                chunk_target_dec = target_dec[j:j_end, i:i_end]
                
                # 展平目标坐标
                ra_flat = chunk_target_ra.ravel()
                dec_flat = chunk_target_dec.ravel()
                
                # 只处理有限值的点
                valid_target_mask = np.isfinite(ra_flat) & np.isfinite(dec_flat)
                valid_indices = np.where(valid_target_mask)[0]
                
                if len(valid_indices) == 0:
                    continue
                
                # 只对有效目标点进行查询
                query_points = np.column_stack([ra_flat[valid_indices], 
                                                dec_flat[valid_indices]])
                
                # 查询最近邻
                distances, indices = tree.query(
                    query_points,
                    k=1, 
                    distance_upper_bound=cfg.coordinate_search_radius
                )
                
                # 创建结果数组
                chunk_result = np.full(ra_flat.shape, np.nan, dtype=np.float32)
                
                # 填充有效查询结果
                valid_query = distances < np.inf
                if np.any(valid_query):
                    chunk_result[valid_indices[valid_query]] = valid_data_sampled[indices[valid_query]]
                
                # 重塑并赋值
                reprojected[j:j_end, i:i_end] = chunk_result.reshape(
                    j_end - j, i_end - i)
        
        # 验证结果
        valid_final = np.sum(~np.isnan(reprojected))
        if valid_final == 0:
            return None
        
        return reprojected
        
    except Exception:
        return None

def reproject_radio_to_aia(radio_data:   np.ndarray,
                           radio_header: fits.Header,
                           ra_map:       Optional[np.ndarray],
                           dec_map:      Optional[np.ndarray],
                           target_shape: Tuple[int, int],
                           aia_wcs_2d:   WCS,
                           cfg:          Config) -> Optional[np.ndarray]:
    """
    简化版：只使用坐标查找表进行重投影
    """
    # 只使用坐标查找表方法
    if ra_map is not None and dec_map is not None:
        return reproject_radio_with_coordinate_lookup(
            radio_data, ra_map, dec_map,
            target_shape, aia_wcs_2d, cfg,
            radio_header=radio_header
        )
    
    return None

# ============================================================
#  展示级等值线平滑（归一化卷积，正确处理 NaN 边界）
# ============================================================
def smooth_for_contour(data: np.ndarray, sigma: float) -> np.ndarray:
    """
    仅用于绘图前展示，不修改分析数据。
    归一化卷积：smooth(data) / smooth(valid_mask)，NaN 区域不扩散。
    scipy.gaussian_filter 比 astropy convolve 快约 10×。
    """
    if sigma <= 0:
        return data
    nan_mask = np.isnan(data)
    filled   = np.where(nan_mask, 0.0, data)
    weights  = (~nan_mask).astype(np.float64)
    smooth_d = gaussian_filter(filled,  sigma=sigma)
    smooth_w = gaussian_filter(weights, sigma=sigma)
    with np.errstate(invalid='ignore', divide='ignore'):
        result = np.where(smooth_w > 1e-6, smooth_d / smooth_w, np.nan)
    return result

# ============================================================
#  波束与颜色工具
# ============================================================
def get_beam_params_from_header(header: fits.Header) -> Optional[Dict]:
    """从 FITS 头提取波束椭圆参数：BMAJ(角秒), BMIN(角秒), BPA(度)。"""
    bmaj = header.get('BMAJ', None)
    bmin = header.get('BMIN', None)
    bpa  = header.get('BPA',  0.0)
    if bmaj is None or bmin is None:
        return None
    return {'bmaj_arcsec': float(bmaj) * 3600.0,
            'bmin_arcsec': float(bmin) * 3600.0,
            'bpa_deg':     float(bpa)}

def draw_beam_ellipse_pixel(ax, beam: Dict, aia_cutout_map: sunpy.map.GenericMap,
                             color: str = 'white'):
    """在图像左下角绘制波束椭圆（像素坐标）。"""
    cdelt   = abs(aia_cutout_map.scale.axis1.to(u.arcsec / u.pix).value)
    bmaj_px = beam['bmaj_arcsec'] / cdelt
    bmin_px = beam['bmin_arcsec'] / cdelt
    ny, nx  = aia_cutout_map.data.shape
    cx_px, cy_px = nx * 0.08, ny * 0.08
    ellipse = Ellipse(
        xy=(cx_px, cy_px), width=bmin_px, height=bmaj_px,
        angle=beam['bpa_deg'], linewidth=1.5,
        edgecolor=color, facecolor='none', alpha=0.85
    )
    ax.add_patch(ellipse)
    ax.text(cx_px, cy_px - bmaj_px * 0.7, 'Beam',
            color=color, fontsize=8, ha='center', va='top', alpha=0.85)

def get_band_color(band_label: str, band_idx: int, cfg: Config,
                   color_cache: Optional[List] = None) -> Tuple[str, str]:
    """根据波段标签返回 (主色, 暗色) 对，优先使用缓存中的精确频率匹配。"""
    m = _RE_MHZ.search(band_label)
    if m and color_cache is not None:
        label_mhz = float(m.group(1))
        for key_mhz, val in color_cache:
            if abs(key_mhz - label_mhz) < 0.5:
                return val
    return cfg.default_colors[band_idx % len(cfg.default_colors)]

def process_hmi_for_overlay(hmi_file: str, target_wcs,
                              cfg: Config) -> Optional[sunpy.map.GenericMap]:
    """
    处理 HMI 磁图：重投影到目标 WCS，高斯平滑，阈值过滤，返回可用于等值线绘制的 map。
    """
    try:
        hmi_map = sunpy.map.Map(hmi_file)
        with sunpy.coordinates.propagate_with_solar_surface():
            aligned = hmi_map.reproject_to(target_wcs)
        smoothed = gaussian_filter(aligned.data, sigma=cfg.hmi_sigma)
        smoothed[np.abs(smoothed) < cfg.hmi_threshold_gauss] = 0
        return sunpy.map.Map(smoothed, aligned.meta)
    except Exception:
        return None

# ============================================================
#  简化核心分组处理逻辑
# ============================================================
def process_aia_group(aia_file:    str,
                       hmi_file:   Optional[str],
                       sub_tasks:  List[Tuple[int, Dict]],
                       task_index: int,
                       total_tasks: int,
                       cfg:         Config,
                       color_cache: List):
    """
    简化版：移除太阳自转修正和高度计算
    """
    check_memory_usage(limit=cfg.memory_limit_pct)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")

    selected_bands_idx: Dict[str, int] = {b: i for i, b in enumerate(cfg.selected_bands)}
    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else 'hot'

    aia_map = cutout_aia = hmi_processed = None

    try:
        aia_map  = sunpy.map.Map(aia_file)
        aia_time = (aia_map.date.to_datetime()
                    if hasattr(aia_map, 'date')
                    else parse_aia_time_from_filename(os.path.basename(aia_file)))

        # 裁剪 ROI
        bl = SkyCoord(Tx=cfg.roi_bottom_left[0] * u.arcsec,
                      Ty=cfg.roi_bottom_left[1] * u.arcsec,
                      frame=aia_map.coordinate_frame)
        tr = SkyCoord(Tx=cfg.roi_top_right[0] * u.arcsec,
                      Ty=cfg.roi_top_right[1] * u.arcsec,
                      frame=aia_map.coordinate_frame)
        cutout_aia = aia_map.submap(bl, top_right=tr)

        # 提取目标形状和WCS
        target_shape = cutout_aia.data.shape
        
        # 简化：直接使用cutout_aia的WCS
        aia_wcs_2d = cutout_aia.wcs

        # 预处理 HMI 磁图（若启用）
        hmi_processed = (process_hmi_for_overlay(hmi_file, cutout_aia.wcs, cfg)
                         if cfg.overlay_hmi and hmi_file else None)

        # 创建输出目录
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)

        # 遍历该 AIA 对应的每个射电时间切片
        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=cfg.memory_limit_pct)
            print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")

            fig = plt.figure(figsize=(12, 10))
            ax  = fig.add_subplot(111, projection=cutout_aia.wcs)

            # --- 1. 绘制 AIA 底图 ---
            cutout_aia.plot(
                axes=ax,
                norm=mcolors.LogNorm(vmin=cfg.aia_vmin, vmax=cfg.aia_vmax),
                cmap=aia_cmap_name,
                title=False
            )
            ax.coords.grid(False)

            legend_handles   = []
            first_radio_time = None
            collected_beams: Dict[str, Dict] = {}

            # --- 2. 叠加 HMI 等值线（正极红，负极蓝）---
            if hmi_processed is not None:
                ax.contour(hmi_processed.data, levels=cfg.hmi_levels_gauss,
                           colors=['red'], linewidths=0.8, alpha=0.7)
                ax.contour(hmi_processed.data,
                           levels=[-lv for lv in cfg.hmi_levels_gauss],
                           colors=['blue'], linewidths=0.8, alpha=0.7)
                legend_handles += [
                    Line2D([0], [0], color='red',  lw=0.8,
                           label=f'+{cfg.hmi_levels_gauss[0]:.0f}G'),
                    Line2D([0], [0], color='blue', lw=0.8,
                           label=f'-{cfg.hmi_levels_gauss[0]:.0f}G'),
                ]

            # 按频率排序波段
            sorted_bands = sorted(single_slice_bands.items(), 
                                  key=lambda x: float(_RE_BAND_SORTED.search(x[0]).group(1)) 
                                  if _RE_BAND_SORTED.search(x[0]) else 0.0)

            # --- 3. 叠加射电等值线（每个波段一种颜色）---
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_band_idx = selected_bands_idx.get(band_label, band_idx)
                main_color, dark_color = get_band_color(
                    band_label, orig_band_idx, cfg, color_cache)

                drawn_any = False
                for fits_path, polarization, radio_time in file_list:
                    if (cfg.polarization_mode != 'BOTH'
                            and polarization != cfg.polarization_mode):
                        continue
                    
                    try:
                        # 提取射电数据和坐标图
                        radio_data_2d, ra_map, dec_map, radio_header_2d, _ = extract_radio_2d_data(
                            fits_path, use_float32=cfg.radio_use_float32, cfg=cfg
                        )
                    
                        if radio_data_2d is None or radio_data_2d.size == 0:
                            continue
                    
                        # 获取波束信息
                        beam = get_beam_params_from_header(radio_header_2d)
                        if beam and band_label not in collected_beams:
                            collected_beams[band_label] = beam
                    
                        # 重投影射电数据到AIA坐标
                        reprojected = reproject_radio_to_aia(
                            radio_data_2d, radio_header_2d,
                            ra_map, dec_map,
                            target_shape, aia_wcs_2d,
                            cfg
                        )
                        
                        if (reprojected is None
                                or np.isnan(np.nanmax(reprojected))
                                or np.nanmax(reprojected) <= 0):
                            continue

                        # 计算等值线级别
                        display_data = smooth_for_contour(reprojected, cfg.contour_smooth_sigma)
                        levels = compute_contour_levels(display_data, cfg)
                        if not levels:
                            continue

                        # 绘制等值线
                        n_lev = len(levels)
                        lws = [cfg.contour_linewidths[min(i, len(cfg.contour_linewidths) - 1)]
                               for i in range(n_lev)]
                        colors_list = [dark_color if i < n_lev - 1 else main_color
                                       for i in range(n_lev)]

                        ax.contour(display_data, levels=levels,
                                   colors=colors_list, linewidths=lws,
                                   alpha=cfg.contour_alpha)

                        if radio_time and first_radio_time is None:
                            first_radio_time = radio_time
                        drawn_any = True

                    except Exception:
                        pass

                if drawn_any:
                    legend_handles.append(
                        Line2D([0], [0], color=main_color, linewidth=2.0,
                               label=f"{band_label}"))

            # --- 4. 绘制波束椭圆（左下角）---
            if cfg.show_beam and collected_beams:
                for b_idx, (b_label, beam) in enumerate(collected_beams.items()):
                    b_color, _ = get_band_color(b_label, b_idx, cfg, color_cache)
                    draw_beam_ellipse_pixel(ax, beam, cutout_aia, color=b_color)

            # --- 5. 绘制日面边缘（太阳轮廓）---
            cutout_aia.draw_limb(axes=ax, color='gray', linewidth=1.0,
                                 linestyle='--', alpha=0.6, label='Solar limb')

            # --- 6. 图例与标题设置 ---
            title_time = (first_radio_time.strftime('%Y-%m-%d %H:%M:%S') + ' UT'
                          if first_radio_time else os.path.basename(aia_file))
            ax.set_title(
                f"AIA 171Å + Radio ({cfg.polarization_mode}) + HMI\n{title_time}",
                fontsize=12, pad=10, color='white'
            )
            ax.legend(handles=legend_handles, loc='upper right',
                      fontsize=9, framealpha=0.6, facecolor='black', labelcolor='white')

            # --- 7. 样式调整与保存 ---
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            ax.tick_params(colors='white', direction='in')
            for spine in ax.spines.values():
                spine.set_edgecolor('white')
            ax.coords[0].set_axislabel('Solar X (arcsec)', color='white')
            ax.coords[1].set_axislabel('Solar Y (arcsec)', color='white')

            if cfg.save_figure:
                radio_time_str = (first_radio_time.strftime('%Y%m%d_%H%M%S')
                                  if first_radio_time else f'unknown_{sub_index}')
                output_filename = (
                    f"{radio_time_str}_{cfg.polarization_mode}_seq{sub_index + 1:02d}.png"
                )
                plt.savefig(
                    os.path.join(cfg.output_dir, output_filename),
                    dpi=cfg.dpi, bbox_inches='tight', facecolor='black'
                )

            fig.clf()
            plt.close(fig)
            gc.collect()

    except Exception:
        import traceback
        traceback.print_exc()

    finally:
        del aia_map, cutout_aia, hmi_processed
        gc.collect()

# ============================================================
#  ★ 优化4：射电头文件并行读取（线程池，I/O 密集型）
# ============================================================
def parse_radio_time_from_header(header: fits.Header) -> Optional[datetime]:
    """从FITS头中解析射电观测时间（支持多种关键字）。"""
    # 尝试多个可能的时间关键字
    time_keys = ['DATE-OBS', 'DATE_OBS', 'DATEOBS', 'DATE-BEG', 'DATE_BEG', 'DATEBEG']
    
    for key in time_keys:
        if key in header:
            date_str = str(header[key]).strip()
            if date_str:
                for fmt in _DATETIME_FMTS:
                    try:
                        # 清理时间字符串
                        date_clean = date_str.replace('Z', '').replace('T', ' ').strip()
                        return datetime.strptime(date_clean, fmt)
                    except ValueError:
                        continue
    
    # 如果所有方法都失败，返回None
    return None

def _read_one_radio_header(rf: str,
                            selected_bands: Tuple[str, ...],
                            pol: str) -> Optional[Dict]:
    """
    优化版：改进时间解析和错误处理
    """
    band_found = next((b for b in selected_bands if b in rf), None)
    if not band_found:
        return None
    try:
        hdr = fits.getheader(rf)
        
        # 使用新的时间解析函数
        r_time = parse_radio_time_from_header(hdr)
        
        if r_time:
            return {'path': rf, 'band': band_found, 'pol': pol, 'time': r_time}
        else:
            # 调试信息：显示无法解析的时间
            date_obs = str(hdr.get('DATE-OBS', '')).strip()
            print(f"    警告: 无法解析射电文件时间: {date_obs}, 文件: {os.path.basename(rf)}")
            
    except Exception as e:
        print(f"    读取射电文件头出错: {os.path.basename(rf)}, 错误: {str(e)[:100]}")
    
    return None

# ============================================================
def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """
    优化版：改进时间匹配逻辑，添加详细调试信息
    """
    print("=" * 60)
    print("正在扫描并进行横向切片匹配，请稍候...")

    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    hmi_files = sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))

    if not aia_files:
        print("[错误] 找不到 AIA 文件，请检查 cfg.aia_base_dir")
        return []

    # 快速测试模式
    if cfg.quick_test:
        print("[快速测试模式] 只处理前几个文件")
        aia_files = aia_files[:min(5, len(aia_files))]

    hmi_times = []
    for hf in hmi_files:
        t = parse_hmi_time_from_filename(os.path.basename(hf))
        if t:
            hmi_times.append((hf, t))

    pol = cfg.polarization_mode
    files_in_pol_dir    = glob.glob(os.path.join(cfg.radio_base_dir, "**", pol, "*.fits"),
                                    recursive=True)
    files_with_pol_name = glob.glob(os.path.join(cfg.radio_base_dir, "**", f"*{pol}*.fits"),
                                    recursive=True)
    
    # 过滤掉坐标图文件
    radio_files = []
    for f in list(set(files_in_pol_dir + files_with_pol_name)):
        if '_RightAscensionDegree.fits' in f or '_DeclinationDegree.fits' in f:
            continue  # 跳过坐标图文件
        radio_files.append(f)
    
    # 快速测试模式
    if cfg.quick_test:
        radio_files = radio_files[:min(10, len(radio_files))]
    
    print(f"成功锁定 {len(radio_files)} 个 {pol} 射电数据文件。正在并发提取观测时间...")

    # ★ 优化4：线程池并发读取头文件
    max_io_threads = min(32, (os.cpu_count() or 4) * 2, max(1, len(radio_files)))
    selected_bands_tuple = tuple(cfg.selected_bands)
    _read_fn = partial(_read_one_radio_header,
                       selected_bands=selected_bands_tuple, pol=pol)

    radio_cache: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_io_threads) as executor:
        results = executor.map(_read_fn, radio_files)
        radio_cache = [r for r in results if r is not None]

    print(f"  读取完毕，有效射电观测记录: {len(radio_cache)} 条")
    
    # 打印时间范围信息
    if radio_cache:
        radio_times = [rc['time'] for rc in radio_cache]
        min_time = min(radio_times)
        max_time = max(radio_times)
        print(f"  射电时间范围: {min_time} 到 {max_time}")

    start_idx        = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx          = cfg.aia_file_end_idx   if cfg.aia_file_end_idx   is not None else len(aia_files)
    target_aia_files = aia_files[start_idx:end_idx]

    hmi_threshold_sec = cfg.hmi_time_threshold * 3600
    grouped_tasks     = []
    
    # 统计信息
    match_stats = {'aia_processed': 0, 'aia_matched': 0, 'total_slices': 0}

    for aia_file in target_aia_files:
        match_stats['aia_processed'] += 1
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
            print(f"  警告: 无法解析AIA文件时间: {os.path.basename(aia_file)}")
            continue

        # 寻找时间上最接近的 HMI 文件
        best_hmi = None
        if hmi_times:
            valid_hmis = [hf for hf in hmi_times
                          if abs((hf[1] - aia_time).total_seconds()) <= hmi_threshold_sec]
            if valid_hmis:
                best_hmi = min(valid_hmis,
                               key=lambda x: abs((x[1] - aia_time).total_seconds()))[0]

        # 收集时间阈值内的射电数据，按波段分组
        band_groups: Dict[str, list] = {}
        for rc in radio_cache:
            time_diff = abs((rc['time'] - aia_time).total_seconds())
            if time_diff <= cfg.radio_time_threshold:
                band_groups.setdefault(rc['band'], []).append(
                    (rc['path'], rc['pol'], rc['time'], time_diff))

        if not band_groups:
            if cfg.debug_mode:
                print(f"  AIA时间 {aia_time}: 无射电数据匹配 (阈值: {cfg.radio_time_threshold}秒)")
            continue

        match_stats['aia_matched'] += 1
        
        # 调试信息：显示每个波段的匹配情况
        if cfg.debug_mode:
            print(f"  AIA时间 {aia_time}:")
            for band, files in band_groups.items():
                print(f"    波段 {band}: {len(files)} 个文件")
                for f in files[:2]:  # 只显示前2个
                    print(f"      时间差: {f[3]:.1f}秒, 文件: {os.path.basename(f[0])}")

        # 匹配阶段排序 + 截断
        for band in band_groups:
            # 按时间差排序，选择最接近的
            band_groups[band].sort(key=lambda x: x[3])  # 按时间差排序
            band_groups[band] = band_groups[band][:cfg.max_radio_per_band]

        # 确定横向切片数量：取所有波段的最小文件数
        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            if cfg.debug_mode:
                print(f"    警告: 某些波段没有匹配文件")
            continue

        # 构建横向切片
        tasks_for_this_aia = []
        for sub_index in range(min_count):
            slice_bands = {}
            for band in band_groups:
                if sub_index < len(band_groups[band]):
                    slice_bands[band] = [band_groups[band][sub_index][:3]]  # 去掉时间差
            
            if slice_bands:  # 确保切片不为空
                tasks_for_this_aia.append((sub_index, slice_bands))
                match_stats['total_slices'] += 1
        
        if tasks_for_this_aia:
            grouped_tasks.append((aia_file, best_hmi, tasks_for_this_aia))
            
            # 打印匹配成功信息
            if cfg.debug_mode:
                print(f"    成功创建 {len(tasks_for_this_aia)} 个切片")

    # 打印统计信息
    print(f"\n匹配结果统计:")
    print(f"  处理的AIA文件: {match_stats['aia_processed']}")
    print(f"  成功匹配的AIA文件: {match_stats['aia_matched']}")
    print(f"  创建的切片总数: {match_stats['total_slices']}")
    print(f"  成功创建了 {len(grouped_tasks)} 组以 AIA 为核心的任务。")
    print("=" * 60)
    return grouped_tasks

# ============================================================
#  ★ 优化1：子进程初始化器
# ============================================================
def _worker_init():
    """
    ProcessPoolExecutor 子进程启动时调用，确保每个 worker 使用非交互式
    Matplotlib 后端（Agg），避免 GUI 资源争用和内存泄漏。
    """
    import matplotlib
    matplotlib.use('Agg')
    import warnings
    warnings.filterwarnings('ignore')

# ============================================================
#  简化主函数
# ============================================================
def main():
    cfg = Config()
    
    # 颜色缓存整个运行只构建一次
    color_cache = _build_band_color_cache(cfg)

    grouped_tasks = build_matched_pairs(cfg)
    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return

    total = len(grouped_tasks)

    # 单进程模式（简化）
    print(f"[模式] 单进程，共 {total} 组任务")
    for task_index, (aia_file, hmi_file, sub_tasks) in enumerate(grouped_tasks):
        process_aia_group(
            aia_file=aia_file,
            hmi_file=hmi_file,
            sub_tasks=sub_tasks,
            task_index=task_index + 1,
            total_tasks=total,
            cfg=cfg,
            color_cache=color_cache,
        )

    print("\n全部任务处理完毕。")

if __name__ == "__main__":
    main()
