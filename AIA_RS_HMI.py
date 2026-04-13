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
from astropy.time import Time as ATime
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.convolution import convolve, Gaussian2DKernel
import sunpy.map
import sunpy.coordinates
from sunpy.coordinates import frames
from reproject import reproject_interp
from scipy.ndimage import shift as nd_shift
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
_DATETIME_FMTS  = [
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
    "%Y%m%d%H%M%S%f",
]

# ============================================================
#  配置类
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

    apply_solar_rotation_correction: bool = True
    reproject_order:     int          = 2
    radio_smooth_sigma:  float        = 1.0   # 重投影后数据级平滑

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

    # ★ 优化1：用户可配核心数；1 = 单进程（调试模式），>1 = 多进程
    num_workers:         int   = 8
    # ★ 优化2：内存占用上限（%），超过则暂停提交新任务或等待释放
    memory_limit_pct:    float = 85.0
    # ★ 优化3：射电数据精度；True = float32（内存减半），False = float64
    radio_use_float32:   bool  = True

    # 新增：通量归一化选项
    flux_normalization: str = 'none'  # 'none', 'peak', 'rms', 'flux_conserved'
    flux_reference_band: Optional[str] = None  # 参考波段，如'300MHz'
    
    # 新增：射电图像预处理选项
    apply_background_subtraction: bool = True
    background_estimation_method: str = 'corner'  # 'corner', 'median', 'minimum'
    
    # 新增：坐标转换精度控制
    coordinate_tolerance: float = 1e-6  # 坐标转换容差
    use_precise_solar_rotation: bool = True  # 使用精确太阳自转模型
    
    # 新增：叠加质量验证
    overlay_validation: bool = True  # 是否验证叠加质量
    min_overlay_correlation: float = 0.2  # 最小相关系数阈值
    reprojection_method: str = 'scientific'  # 'simple', 'interp', 'scientific'

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
    for pat in _RE_AIA_PATS:
        m = pat.search(filename)
        if m:
            ts = m.group(1).replace('Z', '')
            if 'T' in ts:
                d, t = ts.split('T')
                if len(t) == 6 and ':' not in t:
                    t = f"{t[:2]}:{t[2:4]}:{t[4:]}"
                ts = f"{d}T{t}"
            try:
                return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
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
#  射电数据工具
# ============================================================
def extract_radio_2d_data(fits_path: str, use_float32: bool = True) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], fits.Header, Optional[WCS]]:
    """
    增强版：从 FITS HDU 中提取二维射电图像数据和坐标查找表。
    自动查找同目录下的坐标图文件。
    """
    try:
        # 首先读取数据文件
        with fits.open(fits_path) as hdu_data:
            data = hdu_data[0].data
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            header = hdu_data[0].header.copy()
            
            # 确定坐标图文件的基本名称
            base_dir = os.path.dirname(fits_path)
            base_name = os.path.basename(fits_path)
            
            # 移除可能的极化后缀和扩展名，获取频率前缀
            # 例如: "149MHz_20250124_044700_LL.fits" -> "149MHz"
            name_parts = base_name.split('_')
            if len(name_parts) > 0:
                freq_prefix = name_parts[0]  # 如 "149MHz"
            else:
                freq_prefix = os.path.basename(base_dir)  # 使用目录名作为频率前缀
            
            # 查找坐标图文件
            ra_pattern = os.path.join(base_dir, f"{freq_prefix}*RightAscension*.fits")
            dec_pattern = os.path.join(base_dir, f"{freq_prefix}*Declination*.fits")
            
            ra_files = glob.glob(ra_pattern)
            dec_files = glob.glob(dec_pattern)
            
            ra_map = None
            dec_map = None
            
            # 读取赤经坐标图
            if ra_files:
                try:
                    with fits.open(ra_files[0]) as hdu_ra:
                        ra_map = hdu_ra[0].data
                        while ra_map.ndim > 2:
                            ra_map = ra_map[0]
                        ra_map = np.squeeze(ra_map)
                        if use_float32:
                            ra_map = ra_map.astype(np.float32)
                except Exception as e:
                    print(f"    警告: 读取赤经坐标图失败: {e}")
            else:
                # 尝试在上一级目录查找
                parent_dir = os.path.dirname(base_dir)
                parent_ra_pattern = os.path.join(parent_dir, f"{freq_prefix}*RightAscension*.fits")
                parent_ra_files = glob.glob(parent_ra_pattern)
                if parent_ra_files:
                    try:
                        with fits.open(parent_ra_files[0]) as hdu_ra:
                            ra_map = hdu_ra[0].data
                            while ra_map.ndim > 2:
                                ra_map = ra_map[0]
                            ra_map = np.squeeze(ra_map)
                            if use_float32:
                                ra_map = ra_map.astype(np.float32)
                    except Exception as e:
                        print(f"    警告: 读取上级目录赤经坐标图失败: {e}")
            
            # 读取赤纬坐标图
            if dec_files:
                try:
                    with fits.open(dec_files[0]) as hdu_dec:
                        dec_map = hdu_dec[0].data
                        while dec_map.ndim > 2:
                            dec_map = dec_map[0]
                        dec_map = np.squeeze(dec_map)
                        if use_float32:
                            dec_map = dec_map.astype(np.float32)
                except Exception as e:
                    print(f"    警告: 读取赤纬坐标图失败: {e}")
            else:
                # 尝试在上一级目录查找
                parent_dir = os.path.dirname(base_dir)
                parent_dec_pattern = os.path.join(parent_dir, f"{freq_prefix}*Declination*.fits")
                parent_dec_files = glob.glob(parent_dec_pattern)
                if parent_dec_files:
                    try:
                        with fits.open(parent_dec_files[0]) as hdu_dec:
                            dec_map = hdu_dec[0].data
                            while dec_map.ndim > 2:
                                dec_map = dec_map[0]
                            dec_map = np.squeeze(dec_map)
                            if use_float32:
                                dec_map = dec_map.astype(np.float32)
                    except Exception as e:
                        print(f"    警告: 读取上级目录赤纬坐标图失败: {e}")
            
            # 如果找不到坐标图，尝试从数据文件头构建WCS
            radio_wcs_2d = None
            if ra_map is None or dec_map is None:
                radio_wcs_2d = build_radio_wcs_2d(header, None, {})
            
            dtype = np.float32 if use_float32 else np.float64
            return data.astype(dtype), ra_map, dec_map, header, radio_wcs_2d
            
    except Exception as e:
        print(f"读取FITS文件失败 {fits_path}: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None, None

def _get_header_val(header: fits.Header, keys: List[str], default):
    """模块级工具函数，替代 build_radio_wcs_2d 内的嵌套闭包。"""
    for k in keys:
        if k in header and header[k] is not None:
            return header[k]
    return default

def build_radio_wcs_2d(header: fits.Header, obs_time: Optional[datetime],
                        ref_meta: dict) -> WCS:
    """
    根据射电 FITS 头构建二维 WCS，用于后续重投影。
    若缺少必要关键字，则使用合理默认值。
    """
    h = fits.Header()
    h['NAXIS']  = 2
    h['NAXIS1'] = _get_header_val(header, ['NAXIS1'], 1)
    h['NAXIS2'] = _get_header_val(header, ['NAXIS2'], 1)
    h['CRPIX1'] = _get_header_val(header, ['CRPIX1'], h['NAXIS1'] / 2.0)
    h['CRPIX2'] = _get_header_val(header, ['CRPIX2'], h['NAXIS2'] / 2.0)
    h['CRVAL1'] = _get_header_val(header, ['CRVAL1'], 0.0)
    h['CRVAL2'] = _get_header_val(header, ['CRVAL2'], 0.0)
    h['CDELT1'] = _get_header_val(header, ['CDELT1', 'CD1_1'], 1.0)
    h['CDELT2'] = _get_header_val(header, ['CDELT2', 'CD2_2'], 1.0)

    ctype1 = str(_get_header_val(header, ['CTYPE1'], '')).strip().upper()
    if 'RA' in ctype1:
        h['CTYPE1'], h['CTYPE2'] = 'RA---SIN', 'DEC--SIN'
    else:
        h['CTYPE1'], h['CTYPE2'] = 'HPLN-TAN', 'HPLT-TAN'

    cunit = str(_get_header_val(header, ['CUNIT1'], '')).strip().lower()
    if not cunit or cunit == 'none':
        cunit = 'arcsec' if 'HPL' in h['CTYPE1'] else 'deg'
    h['CUNIT1'], h['CUNIT2'] = cunit, cunit

    for k in ['PC1_1', 'PC1_2', 'PC2_1', 'PC2_2']:
        if k in header:
            h[k] = header[k]

    if obs_time:
        h['DATE-OBS'] = obs_time.isoformat()
    elif 'DATE-OBS' in header:
        h['DATE-OBS'] = header['DATE-OBS']

    if ref_meta:
        for k in ['DSUN_OBS', 'HGLN_OBS', 'HGLT_OBS', 'CRLN_OBS', 'CRLT_OBS',
                  'RSUN_REF', 'RSUN_OBS']:
            if k in ref_meta:
                h[k] = ref_meta[k]

    return WCS(h)

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
#  太阳自转修正
# ============================================================
def apply_solar_rotation(coord_hpc: SkyCoord, t_from: datetime, t_to: datetime,
                          height_rsun: float = 1.0) -> SkyCoord:
    """
    将给定日面坐标从 t_from 时刻通过太阳较差自转推算到 t_to 时刻。
    使用 Stonyhurst 经度纬度，考虑纬度相关的自转速率。
    """
    t_from_ap = ATime(t_from.isoformat())
    t_to_ap   = ATime(t_to.isoformat())

    hpc_3d = SkyCoord(
        coord_hpc.Tx, coord_hpc.Ty,
        frame=frames.Helioprojective(obstime=t_from_ap, observer=coord_hpc.observer,
                                     rsun=height_rsun * u.R_sun)
    )
    hgs = hpc_3d.transform_to(frames.HeliographicStonyhurst(obstime=t_from_ap))
    if np.isnan(hgs.lat.value):
        return coord_hpc

    dt_days = (t_to_ap - t_from_ap).to(u.day).value
    sin_lat  = np.sin(hgs.lat.rad)
    omega    = 14.713 - 2.396 * sin_lat**2 - 1.787 * sin_lat**4

    new_hgs = SkyCoord(
        lon=hgs.lon + omega * dt_days * u.deg,
        lat=hgs.lat,
        radius=hgs.radius,
        frame=frames.HeliographicStonyhurst(obstime=t_to_ap)
    )
    return new_hgs.transform_to(frames.Helioprojective(obstime=t_to_ap, observer='earth'))

# ============================================================
#  重投影（接收预提取的 target_shape + aia_wcs_2d）
# ============================================================
def reproject_radio_with_coordinate_lookup(radio_data: np.ndarray,
                                           ra_map: np.ndarray,
                                           dec_map: np.ndarray,
                                           target_shape: Tuple[int, int],
                                           aia_wcs_2d: WCS,
                                           radio_time: Optional[datetime],
                                           aia_time: Optional[datetime],
                                           height_rsun: float,
                                           cfg: Config) -> Optional[np.ndarray]:
    """
    增强版：使用坐标查找表将射电图像重投影到 AIA 裁剪图的 WCS 和形状上。
    添加更多验证和错误处理。
    """
    try:
        if ra_map is None or dec_map is None:
            print("    缺少坐标查找表，无法进行重投影")
            return None
            
        # 确保坐标图与数据形状一致
        if ra_map.shape != radio_data.shape or dec_map.shape != radio_data.shape:
            print(f"    坐标图形状不匹配: 数据{radio_data.shape}, RA{ra_map.shape}, Dec{dec_map.shape}")
            # 尝试调整坐标图形状
            if ra_map.ndim == 3 and ra_map.shape[0] == 1:
                ra_map = ra_map[0, :, :]
                dec_map = dec_map[0, :, :]
            if ra_map.shape != radio_data.shape:
                print(f"    调整后形状仍不匹配，跳过重投影")
                return None
        
        # 检查坐标值范围是否合理（赤经应在0-360度，赤纬应在-90到90度）
        ra_min, ra_max = np.nanmin(ra_map), np.nanmax(ra_map)
        dec_min, dec_max = np.nanmin(dec_map), np.nanmax(dec_map)
        
        if not (0 <= ra_min <= 360 and 0 <= ra_max <= 360):
            print(f"    赤经坐标范围异常: {ra_min:.2f} 到 {ra_max:.2f} 度")
            # 尝试标准化到0-360度
            ra_map = np.mod(ra_map, 360)
        
        if not (-90 <= dec_min <= 90 and -90 <= dec_max <= 90):
            print(f"    赤纬坐标范围异常: {dec_min:.2f} 到 {dec_max:.2f} 度")
            # 如果坐标超出范围，可能需要转换单位
            if dec_max > 90 or dec_min < -90:
                print(f"    赤纬坐标超出正常范围，可能单位为弧度或其他")
                return None
        
        # 创建目标网格
        ny, nx = target_shape
        y_indices, x_indices = np.mgrid[0:ny, 0:nx]
        
        # 获取目标网格的世界坐标（AIA坐标系）
        target_coords = aia_wcs_2d.pixel_to_world(x_indices, y_indices)
        
        # 转换为赤道坐标
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        
        # 转换到赤道坐标系（ICRS）
        target_eq_coords = target_coords.transform_to('icrs')
        target_ra = target_eq_coords.ra.deg.reshape(ny, nx)
        target_dec = target_eq_coords.dec.deg.reshape(ny, nx)
        
        # 对坐标图进行网格化，创建插值器
        from scipy.interpolate import griddata
        
        # 获取有效数据点
        valid_mask = ~np.isnan(ra_map) & ~np.isnan(dec_map) & ~np.isnan(radio_data)
        
        if not np.any(valid_mask):
            print("    没有有效的坐标数据点")
            return None
        
        # 提取有效点的坐标和数据
        valid_ra = ra_map[valid_mask]
        valid_dec = dec_map[valid_mask]
        valid_data = radio_data[valid_mask]
        
        # 检查坐标范围
        ra_range = np.nanmax(valid_ra) - np.nanmin(valid_ra)
        dec_range = np.nanmax(valid_dec) - np.nanmin(valid_dec)
        
        if ra_range < 1e-6 or dec_range < 1e-6:
            print(f"    坐标范围过小: RA范围{ra_range:.6f}度, Dec范围{dec_range:.6f}度")
            return None
        
        # 将目标坐标插值到射电数据的坐标网格
        # 由于坐标查找表不是规则的网格，使用线性插值
        try:
            reprojected = griddata(
                (valid_ra, valid_dec),  # 已知点的坐标
                valid_data,             # 已知点的值
                (target_ra, target_dec), # 要插值的点
                method='linear',
                fill_value=np.nan
            )
        except Exception as e:
            print(f"    网格插值失败: {e}")
            # 尝试使用最近邻插值
            reprojected = griddata(
                (valid_ra, valid_dec),
                valid_data,
                (target_ra, target_dec),
                method='nearest',
                fill_value=np.nan
            )
        
        # 应用太阳自转修正（如果启用）
        if (cfg.apply_solar_rotation_correction
                and radio_time and aia_time
                and abs((aia_time - radio_time).total_seconds()) > 1.0):
            
            try:
                # 获取射电图像有效区域的质心
                valid_mask = ~np.isnan(radio_data)
                if np.any(valid_mask):
                    y_indices, x_indices = np.where(valid_mask)
                    center_y = np.mean(y_indices)
                    center_x = np.mean(x_indices)
                    
                    # 使用坐标查找表获取中心点的世界坐标
                    center_ra = ra_map[int(center_y), int(center_x)]
                    center_dec = dec_map[int(center_y), int(center_x)]
                    
                    # 创建SkyCoord对象
                    center_world = SkyCoord(
                        ra=center_ra * u.deg,
                        dec=center_dec * u.deg,
                        frame='icrs'
                    )
                    
                    # 转换到日面经纬度坐标
                    from sunpy.coordinates import frames
                    center_hgs = center_world.transform_to(
                        frames.HeliographicStonyhurst(obstime=ATime(radio_time.isoformat())))
                    
                    # 计算时间差
                    time_diff = (aia_time - radio_time).total_seconds()
                    
                    # 计算自转修正（较差自转）
                    lat_rad = center_hgs.lat.radian
                    omega_deg_per_day = 14.713 - 2.396 * np.sin(lat_rad)**2 - 1.787 * np.sin(lat_rad)**4
                    delta_lon = omega_deg_per_day * (time_diff / 86400.0)  # 经度变化
                    
                    # 应用修正
                    new_hgs = SkyCoord(
                        lon=center_hgs.lon + delta_lon * u.deg,
                        lat=center_hgs.lat,
                        radius=center_hgs.radius,
                        frame=frames.HeliographicStonyhurst(obstime=ATime(aia_time.isoformat()))
                    )
                    
                    # 转换回日面投影坐标
                    new_hpc = new_hgs.transform_to(
                        frames.Helioprojective(obstime=ATime(aia_time.isoformat()),
                                               observer='earth'))
                    
                    # 转换到赤道坐标
                    new_eq = new_hpc.transform_to('icrs')
                    
                    # 计算坐标偏移
                    delta_ra = new_eq.ra.deg - center_ra
                    delta_dec = new_eq.dec.deg - center_dec
                    
                    if abs(delta_ra) >= 0.001 or abs(delta_dec) >= 0.001:
                        # 在目标坐标上应用偏移
                        shifted_ra = target_ra - delta_ra
                        shifted_dec = target_dec - delta_dec
                        
                        # 重新插值
                        try:
                            reprojected = griddata(
                                (valid_ra, valid_dec),
                                valid_data,
                                (shifted_ra, shifted_dec),
                                method='linear',
                                fill_value=np.nan
                            )
                        except:
                            # 如果线性插值失败，使用最近邻
                            reprojected = griddata(
                                (valid_ra, valid_dec),
                                valid_data,
                                (shifted_ra, shifted_dec),
                                method='nearest',
                                fill_value=np.nan
                            )
                            
            except Exception as e:
                print(f"    自转修正失败: {e}")
        
        # 应用数据级平滑
        if cfg.radio_smooth_sigma > 0:
            from scipy.ndimage import gaussian_filter
            reprojected = gaussian_filter(
                np.nan_to_num(reprojected, nan=0.0),
                sigma=cfg.radio_smooth_sigma
            )
            
        # 应用通量守恒归一化（如果启用）
        if hasattr(cfg, 'flux_normalization') and cfg.flux_normalization == 'flux_conserved':
            original_sum = np.nansum(radio_data)
            new_sum = np.nansum(reprojected)
            if new_sum > 0 and original_sum > 0:
                reprojected = reprojected * (original_sum / new_sum)
                
        return reprojected
        
    except Exception as e:
        print(f"    坐标查找表重投影失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def reproject_radio_to_aia_standard(radio_data:   np.ndarray,
                                    radio_header: fits.Header,
                                    radio_wcs:    WCS,
                                    target_shape: Tuple[int, int],
                                    aia_wcs_2d:   WCS,
                                    radio_time:   Optional[datetime],
                                    aia_time:     Optional[datetime],
                                    height_rsun:  float,
                                    cfg:          Config) -> Optional[np.ndarray]:
    """
    将射电图像重投影到 AIA 裁剪图的 WCS 和形状上（标准WCS方法）。
    可选：太阳自转修正、数据级平滑。
    ★ 优化3：reproject 输入为 float32，输出也是 float32；
    smooth 前转 float64 以保持精度。
    """
    try:
        # 尝试使用更精确的重投影方法
        from reproject import reproject_exact
        reprojected, footprint = reproject_exact(
            (radio_data, radio_wcs), aia_wcs_2d,
            shape_out=target_shape,
            return_footprint=True
        )
    except Exception:
        # 如果精确重投影失败，回退到插值方法，使用更高阶插值
        try:
            reprojected, footprint = reproject_interp(
                (radio_data, radio_wcs), aia_wcs_2d,
                shape_out=target_shape, order=3  # 使用3阶插值提高精度
            )
        except Exception as e:
            print(f"    [警告] WCS 重投影失败: {e}")
            return None

    reprojected[footprint == 0] = np.nan

    if (cfg.apply_solar_rotation_correction
            and radio_time and aia_time
            and abs((aia_time - radio_time).total_seconds()) > 1.0):
        try:
            # 获取射电图像有效区域的质心
            valid_mask = ~np.isnan(radio_data)
            if np.any(valid_mask):
                y_indices, x_indices = np.where(valid_mask)
                center_y = np.mean(y_indices)
                center_x = np.mean(x_indices)
                
                # 获取中心点的世界坐标
                center_world = radio_wcs.pixel_to_world(center_x, center_y)
                
                # 应用更精确的自转修正
                from sunpy.coordinates import frames
                import astropy.units as u
                
                # 转换到日面经纬度坐标
                center_hgs = center_world.transform_to(
                    frames.HeliographicStonyhurst(obstime=ATime(radio_time.isoformat())))
                
                # 计算时间差
                time_diff = (aia_time - radio_time).total_seconds()
                
                # 计算自转修正（较差自转）
                lat_rad = center_hgs.lat.radian
                omega_deg_per_day = 14.713 - 2.396 * np.sin(lat_rad)**2 - 1.787 * np.sin(lat_rad)**4
                delta_lon = omega_deg_per_day * (time_diff / 86400.0)  # 经度变化
                
                # 应用修正
                new_hgs = SkyCoord(
                    lon=center_hgs.lon + delta_lon * u.deg,
                    lat=center_hgs.lat,
                    radius=center_hgs.radius,
                    frame=frames.HeliographicStonyhurst(obstime=ATime(aia_time.isoformat()))
                )
                
                # 转换回日面投影坐标
                new_hpc = new_hgs.transform_to(
                    frames.Helioprojective(obstime=ATime(aia_time.isoformat()),
                                           observer='earth'))
                
                # 计算像素偏移
                new_pixel = aia_wcs_2d.world_to_pixel(new_hpc)
                old_pixel = aia_wcs_2d.world_to_pixel(center_world)
                
                shift_x = float(new_pixel[0] - old_pixel[0])
                shift_y = float(new_pixel[1] - old_pixel[1])
                
                if abs(shift_x) >= 0.1 or abs(shift_y) >= 0.1:
                    # 应用偏移，使用3阶插值
                    reprojected = nd_shift(
                        np.nan_to_num(reprojected, nan=0.0),
                        shift=[shift_y, shift_x],
                        order=3,
                        mode='constant',
                        cval=np.nan
                    )
        except Exception as e:
            print(f"    自转修正失败: {e}")
            # 回退到原来的简单方法
            try:
                sky_center = radio_wcs.pixel_to_world(radio_wcs.wcs.crpix[0] - 1,
                                                       radio_wcs.wcs.crpix[1] - 1)
                hpc_radio    = sky_center.transform_to(
                    frames.Helioprojective(obstime=ATime(radio_time.isoformat()),
                                           observer='earth'))
                hpc_aia_time = apply_solar_rotation(hpc_radio, radio_time, aia_time,
                                                     height_rsun)
                px_radio = aia_wcs_2d.world_to_pixel(hpc_radio)
                px_aia   = aia_wcs_2d.world_to_pixel(hpc_aia_time)
                shift_x  = float(px_aia[0] - px_radio[0])
                shift_y  = float(px_aia[1] - px_radio[1])

                if abs(shift_x) >= 0.05 or abs(shift_y) >= 0.05:
                    reprojected = nd_shift(
                        np.nan_to_num(reprojected, nan=0.0),
                        shift=[shift_y, shift_x], order=1,
                        mode='constant', cval=np.nan
                    )
            except Exception:
                pass

    # ★ 优化3：平滑前转 float64 保证精度
    if cfg.radio_smooth_sigma > 0:
        # 如果有波束信息，使用各向异性平滑
        beam_info = get_beam_params_from_header(radio_header)
        if beam_info:
            # 创建各向异性高斯核
            from astropy.convolution import Gaussian2DKernel
            
            # 将波束大小转换为像素
            cdelt = abs(aia_wcs_2d.wcs.cdelt[0] * 3600)  # 度转角秒
            bmaj_pix = beam_info['bmaj_arcsec'] / cdelt
            bmin_pix = beam_info['bmin_arcsec'] / cdelt
            
            # 创建椭圆高斯核
            kernel = Gaussian2DKernel(
                x_stddev=bmin_pix/2.355,  # FWHM转sigma
                y_stddev=bmaj_pix/2.355,
                theta=np.deg2rad(beam_info['bpa_deg'])
            )
            reprojected = convolve(reprojected.astype(np.float64), kernel,
                                   preserve_nan=True)
        else:
            # 使用各向同性高斯平滑
            reprojected = convolve(reprojected.astype(np.float64),
                                   _make_gaussian_kernel(cfg.radio_smooth_sigma),
                                   preserve_nan=True)
    
    # 应用通量守恒归一化（如果启用）
    if hasattr(cfg, 'flux_normalization') and cfg.flux_normalization == 'flux_conserved':
        original_sum = np.nansum(radio_data)
        new_sum = np.nansum(reprojected)
        if new_sum > 0 and original_sum > 0:
            reprojected = reprojected * (original_sum / new_sum)
    
    return reprojected

def reproject_radio_to_aia(radio_data:   np.ndarray,
                           radio_header: fits.Header,
                           radio_wcs:    Optional[WCS],
                           ra_map:       Optional[np.ndarray],
                           dec_map:      Optional[np.ndarray],
                           target_shape: Tuple[int, int],
                           aia_wcs_2d:   WCS,
                           radio_time:   Optional[datetime],
                           aia_time:     Optional[datetime],
                           height_rsun:  float,
                           cfg:          Config) -> Optional[np.ndarray]:
    """
    将射电图像重投影到 AIA 裁剪图的 WCS 和形状上。
    现在支持两种模式：
    1. 标准WCS重投影（当radio_wcs有效时）
    2. 坐标查找表重投影（当ra_map和dec_map有效时）
    """
    # 优先使用坐标查找表（如果可用）
    if ra_map is not None and dec_map is not None:
        return reproject_radio_with_coordinate_lookup(
            radio_data, ra_map, dec_map,
            target_shape, aia_wcs_2d,
            radio_time, aia_time, height_rsun, cfg
        )
    # 否则使用标准WCS重投影
    elif radio_wcs is not None:
        return reproject_radio_to_aia_standard(
            radio_data, radio_header, radio_wcs,
            target_shape, aia_wcs_2d,
            radio_time, aia_time, height_rsun, cfg
        )
    else:
        print("    无法进行重投影：既没有WCS也没有坐标查找表")
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

@lru_cache(maxsize=256)
def corona_height_from_freq(freq_mhz: float) -> float:
    """根据频率估算日冕发射高度（经验公式）。"""
    try:
        val = 4.32 / np.log10((freq_mhz * 1e6 / 8980.0) ** 2 / 4.2e4)
        return max(val, 1.0) if np.isfinite(val) else float('nan')
    except Exception:
        return float('nan')

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
#  核心分组处理逻辑
# ============================================================
def process_aia_group(aia_file:    str,
                       hmi_file:   Optional[str],
                       sub_tasks:  List[Tuple[int, Dict]],
                       task_index: int,
                       total_tasks: int,
                       cfg:         Config,
                       color_cache: List):
    """
    单个 AIA 图像 + 其所有射电时间切片。
    AIA 底图、HMI、aia_wcs_2d 只准备一次，全部子帧复用后彻底释放。
    ★ 优化5：子进程通过 _worker_init 已设置 Agg 后端，无需额外处理。
    """
    check_memory_usage(limit=cfg.memory_limit_pct)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")

    # O(1) 字典，替代 list.index() O(n)
    selected_bands_idx: Dict[str, int] = {b: i for i, b in enumerate(cfg.selected_bands)}

    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else 'hot'

    aia_map = cutout_aia = hmi_processed = None

    try:
        aia_map  = sunpy.map.Map(aia_file)
        aia_time = (aia_map.date.to_datetime()
                    if hasattr(aia_map, 'date')
                    else parse_aia_time_from_filename(os.path.basename(aia_file)))

        # 曝光时间归一化（若存在）
        if (hasattr(aia_map, 'exposure_time')
                and aia_map.exposure_time is not None
                and aia_map.exposure_time.to(u.s).value > 0):
            aia_map = sunpy.map.Map(
                aia_map.data / aia_map.exposure_time.to(u.s).value, aia_map.meta)

        # 裁剪 ROI
        bl = SkyCoord(Tx=cfg.roi_bottom_left[0] * u.arcsec,
                      Ty=cfg.roi_bottom_left[1] * u.arcsec,
                      frame=aia_map.coordinate_frame)
        tr = SkyCoord(Tx=cfg.roi_top_right[0] * u.arcsec,
                      Ty=cfg.roi_top_right[1] * u.arcsec,
                      frame=aia_map.coordinate_frame)
        cutout_aia = aia_map.submap(bl, top_right=tr)

        # 提前提取一次，全部子帧/波段/fits 复用
        target_shape = cutout_aia.data.shape
        aia_wcs_2d   = cutout_aia.wcs
        if aia_wcs_2d.world_n_dim > 2:
            aia_wcs_2d = aia_wcs_2d.celestial
        target_wcs = cutout_aia.wcs

        # 预处理 HMI 磁图（若启用）
        hmi_processed = (process_hmi_for_overlay(hmi_file, target_wcs, cfg)
                         if cfg.overlay_hmi and hmi_file else None)

        # makedirs 移出子帧循环，每组 AIA 最多执行一次
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)

        # 遍历该 AIA 对应的每个射电时间切片
        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=cfg.memory_limit_pct)
            print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")

            fig = plt.figure(figsize=(12, 10))
            ax  = fig.add_subplot(111, projection=target_wcs)

            # --- 1. 绘制 AIA 底图（对数亮度，作为背景）---
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

            def _band_freq_key(item: Tuple[str, list]) -> float:
                mobj = _RE_BAND_SORTED.search(item[0])
                return float(mobj.group(1)) if mobj else 0.0

            sorted_bands = sorted(single_slice_bands.items(), key=_band_freq_key)

            # --- 3. 叠加射电等值线（每个波段一种颜色）---
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_band_idx = selected_bands_idx.get(band_label, band_idx)
                main_color, dark_color = get_band_color(
                    band_label, orig_band_idx, cfg, color_cache)

                freq_match  = _RE_MHZ.search(band_label)
                freq_mhz    = float(freq_match.group(1)) if freq_match else None
                height_rsun = corona_height_from_freq(freq_mhz) if freq_mhz else 1.0

                drawn_any = False
                for fits_path, polarization, radio_time in file_list:
                    if (cfg.polarization_mode != 'BOTH'
                            and polarization != cfg.polarization_mode):
                        continue
                    try:
                        # 使用增强的 extract_radio_2d_data 函数
                        radio_data_2d, ra_map, dec_map, radio_header_2d, radio_wcs_2d = extract_radio_2d_data(
                            fits_path, use_float32=cfg.radio_use_float32
                        )
                    
                        if radio_data_2d is None or radio_data_2d.size == 0:
                            continue
                    
                        # 如果 extract_radio_2d_data 未能构建 WCS，尝试构建
                        if radio_wcs_2d is None:
                            radio_wcs_2d = build_radio_wcs_2d(
                                radio_header_2d, radio_time, cutout_aia.meta
                            )
                    
                        beam = get_beam_params_from_header(radio_header_2d)
                    
                        if beam and band_label not in collected_beams:
                            collected_beams[band_label] = beam
                    
                        reprojected = reproject_radio_to_aia(
                            radio_data_2d, radio_header_2d, radio_wcs_2d,
                            ra_map, dec_map,  # 新增参数
                            target_shape, aia_wcs_2d,
                            radio_time, aia_time, height_rsun, cfg
                        )
                        if (reprojected is None
                                or np.isnan(np.nanmax(reprojected))
                                or np.nanmax(reprojected) <= 0):
                            continue

                        # 叠加质量验证（如果启用）
                        if cfg.overlay_validation:
                            from scipy.signal import correlate2d
                            # 提取小区域进行验证
                            sub_size = min(100, reprojected.shape[0]//4, reprojected.shape[1]//4)
                            center_y, center_x = reprojected.shape[0]//2, reprojected.shape[1]//2
                            
                            aia_sub = cutout_aia.data[
                                center_y-sub_size:center_y+sub_size,
                                center_x-sub_size:center_x+sub_size
                            ]
                            radio_sub = reprojected[
                                center_y-sub_size:center_y+sub_size,
                                center_x-sub_size:center_x+sub_size
                            ]
                            
                            aia_sub = np.nan_to_num(aia_sub, nan=0.0)
                            radio_sub = np.nan_to_num(radio_sub, nan=0.0)
                            
                            if np.sum(aia_sub) > 0 and np.sum(radio_sub) > 0:
                                corr = correlate2d(aia_sub, radio_sub, mode='same')
                                max_corr = np.max(corr)
                                if max_corr > 0:
                                    # 计算归一化相关系数
                                    aia_norm = (aia_sub - np.mean(aia_sub)) / np.std(aia_sub)
                                    radio_norm = (radio_sub - np.mean(radio_sub)) / np.std(radio_sub)
                                    correlation = np.corrcoef(aia_norm.ravel(), radio_norm.ravel())[0, 1]
                                    
                                    if abs(correlation) < cfg.min_overlay_correlation:
                                        print(f"    波段 {band_label} 叠加质量较差，相关系数: {correlation:.3f}")
                                        continue

                        # 展示级平滑（不修改 reprojected 本体）
                        display_data = smooth_for_contour(reprojected,
                                                          cfg.contour_smooth_sigma)
                        levels = compute_contour_levels(display_data, cfg)
                        if not levels:
                            continue

                        n_lev       = len(levels)
                        lws         = [cfg.contour_linewidths[
                                           min(i, len(cfg.contour_linewidths) - 1)]
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
                    h_label = (f" (~{height_rsun:.2f}R☉)"
                               if freq_mhz and np.isfinite(height_rsun) else "")
                    legend_handles.append(
                        Line2D([0], [0], color=main_color, linewidth=2.0,
                               label=f"{band_label}{h_label}"))

            # --- 4. 绘制波束椭圆（左下角）---
            if cfg.show_beam and collected_beams:
                for b_idx, (b_label, beam) in enumerate(collected_beams.items()):
                    b_color, _ = get_band_color(b_label, b_idx, cfg, color_cache)
                    draw_beam_ellipse_pixel(ax, beam, cutout_aia, color=b_color)

            # --- 5. 绘制日面边缘（太阳轮廓）---
            cutout_aia.draw_limb(axes=ax, color='gray', linewidth=1.0,
                                 linestyle='--', alpha=0.6, label='Solar limb')

            # --- 6. 图例与标题设置 ---
            title_time = (first_radio_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UT'
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
                radio_time_str = (first_radio_time.strftime('%Y%m%d_%H%M%S_%f')[:-3]
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
def _read_one_radio_header(rf: str,
                            selected_bands: Tuple[str, ...],
                            pol: str) -> Optional[Dict]:
    """
    读取单个射电 FITS 文件的头文件并解析时间。
    设计为可被 ThreadPoolExecutor 并发调用的顶层函数（可 pickle）。
    """
    band_found = next((b for b in selected_bands if b in rf), None)
    if not band_found:
        return None
    try:
        hdr      = fits.getheader(rf)
        date_obs = str(hdr.get('DATE-OBS', '')).strip()
        r_time   = None
        for fmt in _DATETIME_FMTS:
            try:
                r_time = datetime.strptime(date_obs, fmt)
                break
            except ValueError:
                continue
        if r_time:
            return {'path': rf, 'band': band_found, 'pol': pol, 'time': r_time}
    except Exception:
        pass
    return None

# ============================================================
def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """
    扫描并匹配 AIA 图像与射电数据、HMI 磁图。
    返回任务列表，每个元素为 (aia_file, hmi_file, sub_tasks)。
    ★ 优化4：fits.getheader 改为线程池并发读取，显著缩短扫描时间。
    """
    print("=" * 60)
    print("正在扫描并进行横向切片匹配，请稍候...")

    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    hmi_files = sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))

    if not aia_files:
        print("[错误] 找不到 AIA 文件，请检查 cfg.aia_base_dir")
        return []

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
        # 只保留数据文件
        # 检查文件大小，避免太小的文件（可能是坐标图）
        try:
            if os.path.getsize(f) > 1000:  # 最小文件大小阈值
                radio_files.append(f)
        except:
            radio_files.append(f)
    
    print(f"成功锁定 {len(radio_files)} 个 {pol} 射电数据文件（已排除坐标图文件）。正在并发提取观测时间...")

    # ★ 优化4：线程池并发读取头文件（I/O 密集，线程安全）
    #   线程数取 min(32, cpu_count*2, 文件数)，避免创建过多线程
    max_io_threads = min(32, (os.cpu_count() or 4) * 2, max(1, len(radio_files)))
    selected_bands_tuple = tuple(cfg.selected_bands)   # tuple 可 hash，便于 partial
    _read_fn = partial(_read_one_radio_header,
                       selected_bands=selected_bands_tuple, pol=pol)

    radio_cache: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_io_threads) as executor:
        results = executor.map(_read_fn, radio_files)
        radio_cache = [r for r in results if r is not None]

    print(f"  读取完毕，有效射电观测记录: {len(radio_cache)} 条")

    start_idx        = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx          = cfg.aia_file_end_idx   if cfg.aia_file_end_idx   is not None else len(aia_files)
    target_aia_files = aia_files[start_idx:end_idx]

    hmi_threshold_sec = cfg.hmi_time_threshold * 3600
    grouped_tasks     = []

    for aia_file in target_aia_files:
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
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
            if abs((rc['time'] - aia_time).total_seconds()) <= cfg.radio_time_threshold:
                band_groups.setdefault(rc['band'], []).append(
                    (rc['path'], rc['pol'], rc['time']))

        if not band_groups:
            continue

        # 匹配阶段排序 + 截断，process 时无需每帧重复 sorted()
        for band in band_groups:
            band_groups[band].sort(key=lambda x: x[2])
            band_groups[band] = band_groups[band][:cfg.max_radio_per_band]

        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            continue

        # 构建横向切片：每个切片包含每个波段的第 i 个观测
        tasks_for_this_aia = [
            (sub_index,
             {band: [band_groups[band][sub_index]] for band in band_groups})
            for sub_index in range(min_count)
        ]
        grouped_tasks.append((aia_file, best_hmi, tasks_for_this_aia))

    print(f"\n匹配切片完毕！共成功创建了 {len(grouped_tasks)} 组以 AIA 为核心的任务。")
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
def main():
    cfg = Config()

    # 颜色缓存整个运行只构建一次
    color_cache = _build_band_color_cache(cfg)

    grouped_tasks = build_matched_pairs(cfg)
    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return

    total = len(grouped_tasks)

    # ★ 优化1：根据 num_workers 选择单进程或多进程模式
    if cfg.num_workers <= 1:
        # ── 单进程模式（调试友好，异常信息完整）──────────────────────
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
    else:
        # ── 多进程模式（并行加速）──────────────────────────────────────
        print(f"[模式] 多进程，核心数={cfg.num_workers}，共 {total} 组任务")
        print(f"[内存] 内存占用上限={cfg.memory_limit_pct}%")

        with ProcessPoolExecutor(max_workers=cfg.num_workers,
                                  initializer=_worker_init) as executor:
            # 逐一提交任务；每次提交前检查内存，防止大批任务同时驻留
            futures: Dict = {}
            for task_index, (aia_file, hmi_file, sub_tasks) in enumerate(grouped_tasks):

                # ★ 优化2：提交前检查内存，避免排队任务撑爆内存
                check_memory_usage(limit=cfg.memory_limit_pct)

                fut = executor.submit(
                    process_aia_group,
                    aia_file, hmi_file, sub_tasks,
                    task_index + 1, total,
                    cfg, color_cache,
                )
                futures[fut] = task_index + 1

            # 等待所有任务完成，捕获子进程异常
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    fut.result()
                    print(f"[完成] 任务 {idx}/{total}")
                except Exception as exc:
                    print(f"[错误] 任务 {idx}/{total} 失败: {exc}")

    print("\n全部任务处理完毕。")

if __name__ == "__main__":
    main()
