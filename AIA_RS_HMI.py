# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 22:57:26 2026

@author: Severus

================================================================================
【图像叠加方法说明】
================================================================================
本程序实现太阳多波段观测数据的叠加绘图，将 AIA 171Å EUV 图像、射电成像观测（MUSER 等）
以及 HMI 磁图叠加在同一张图中。叠加顺序和核心步骤如下：

1. **底图绘制（AIA 171Å）**
   - 读取 AIA FITS 文件，生成 sunpy.map.GenericMap 对象。
   - 根据配置的 ROI（底部左下角、右上角坐标）裁剪出日面局部区域。
   - 使用对数归一化（LogNorm）和 SDO AIA 171Å 专用颜色表显示，作为图像背景。

2. **HMI 磁图叠加（可选）**
   - 读取 HMI 磁图 FITS 文件，利用 sunpy.map 的 `reproject_to()` 方法将磁图重投影到
     与 AIA 裁剪后相同的 WCS 投影和像素网格上。
   - 对重投影后的数据进行高斯平滑（sigma 可配），并过滤低于阈值的弱信号。
   - 绘制正、负磁图等值线（正极红色，负极蓝色），叠加在 AIA 底图之上。

3. **射电成像数据叠加**
   - 对每一个选定的射电频率波段（如 149MHz、164MHz 等），读取其 FITS 文件。
   - 从 FITS 头中提取观测时间、WCS 信息、波束参数（BMAJ, BMIN, BPA）。
   - 使用 `reproject_interp` 将射电图像重投影到 AIA 裁剪图的 WCS 和目标形状上。
   - 若启用太阳自转修正，计算从射电观测时刻到 AIA 观测时刻的日面自转位移，
     对重投影后的图像进行亚像素平移。
   - 对重投影数据进行可选的高斯平滑（数据级）。
   - 根据配置的归一化模式（peak 或 rms）计算等值线层级：
        * peak 模式：层级 = 峰值 × 百分比（如 [0.95]）。
        * rms 模式：先估计图像角部噪声 RMS，层级 = RMS × 倍数（如 [5,15,30]）。
   - 绘制等值线，不同波段使用不同颜色（主色和暗色区分内外层），叠加在 HMI 等值线之上。
   - 若配置显示波束椭圆，根据 FITS 头中的波束参数和 AIA 图像尺度，在左下角绘制
     对应颜色的椭圆，标注“Beam”。

4. **时间匹配与序列切片**
   - 扫描射电数据目录，提取每个 FITS 文件的观测时间和所属频率波段。
   - 对每张 AIA 图像，查找时间差在阈值内的所有射电数据，按波段分组。
   - 在每个波段组内，将射电数据按时间排序并截取前 N 个（max_radio_per_band）。
   - 取所有波段的最小切片长度，生成“横向切片”：每个切片包含每个波段的一个观测时刻，
     且这些时刻在时间上对齐（按索引位置匹配）。
   - 对于每个 AIA 图像 + 其对应的切片列表，依次绘制每一帧：AIA 底图 + HMI 等值线 +
     所有波段的射电等值线 + 波束椭圆 + 日面边缘。

5. **绘图与输出**
   - 所有叠加元素绘制在同一 WCS 投影坐标系中，坐标轴单位为角秒（arcsec）。
   - 图标题显示射电观测时间、偏振模式等。
   - 图例展示各波段的频率及其对应的日冕高度（根据频率经验公式估算）。
   - 最终输出 PNG 图片，保存至配置的输出目录。

================================================================================
"""

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
from astropy.time import Time as ATime          # 修复5：移至模块顶层
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
from functools import lru_cache
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
    radio_base_dir: str = r'D:\spike_topping_type_III\2025\20250503\20250503UT071600-072600'
    aia_base_dir:   str = r'D:\spike_topping_type_III\2025\20250503\AIA\171'
    hmi_base_dir:   str = r'D:\spike_topping_type_III\2025\20250503\AIA\hmi'
    output_dir:     str = r'D:\spike_topping_type_III\2025\20250503\overlap\LL'

    save_figure:        bool          = True
    dpi:                int           = 300
    aia_file_start_idx: int           = 105
    aia_file_end_idx:   Optional[int] = 115

    selected_bands:      List[str]    = field(default_factory=lambda: [
        '149MHz', '164MHz', '190MHz', '223MHz', '238MHz', '300MHz'])
    polarization_mode:   str          = 'LL'
    radio_time_threshold: int         = 6
    max_radio_per_band:  int          = 28

    normalization_mode:  str          = 'peak'          # 'peak' 或 'rms'
    contour_levels_peak: List[float]  = field(default_factory=lambda: [0.95])
    rms_sigma_levels:    List[float]  = field(default_factory=lambda: [5.0, 15.0, 30.0])
    rms_box_fraction:    float        = 0.15

    contour_linewidths:  List[float]  = field(default_factory=lambda: [2.0])
    contour_alpha:       float        = 0.90
    contour_smooth_sigma: float       = 0   #3.0 is original 展示级平滑 sigma（像素），0 = 关闭

    apply_solar_rotation_correction: bool = True
    reproject_order:     int          = 2 # 1 is original
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
    roi_bottom_left: List[float] = field(default_factory=lambda: [-900, -300])
    roi_top_right:   List[float] = field(default_factory=lambda: [100,  600])

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

# ============================================================
#  颜色缓存（修复7）
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
#  Gaussian 核缓存（修复6）
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
def extract_radio_2d_data(hdu) -> Tuple[np.ndarray, fits.Header]:
    """从 FITS HDU 中提取二维射电图像数据（自动压缩高维）。"""
    data = hdu.data
    while data.ndim > 2:
        data = data[0]
    return np.squeeze(data).astype(np.float64), hdu.header.copy()

def _get_header_val(header: fits.Header, keys: List[str], default):
    """修复13：模块级工具函数，替代 build_radio_wcs_2d 内的嵌套闭包。"""
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
    corners = [data[:by, :bx], data[:by, -bx:], data[-by:, :bx], data[-by:, -bx:]]
    edge_pixels = np.concatenate([c.ravel() for c in corners])
    edge_pixels = edge_pixels[np.isfinite(edge_pixels)]
    if len(edge_pixels) == 0:
        return float(np.nanstd(data) * 0.1)
    for _ in range(3):
        med = np.median(edge_pixels)
        std = np.std(edge_pixels)
        edge_pixels = edge_pixels[np.abs(edge_pixels - med) < 3 * std]
    return float(np.std(edge_pixels)) if len(edge_pixels) > 0 else float(np.nanstd(data) * 0.1)

def compute_contour_levels(data: np.ndarray, cfg: Config) -> List[float]:
    """支持 normalization_mode='peak'（默认）和 'rms' 两种模式。"""
    finite_data = data[np.isfinite(data)]
    if len(finite_data) == 0:
        return []

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
#  太阳自转修正（修复5/12）
# ============================================================
def apply_solar_rotation(coord_hpc: SkyCoord, t_from: datetime, t_to: datetime,
                          height_rsun: float = 1.0) -> SkyCoord:
    """
    将给定日面坐标从 t_from 时刻通过太阳较差自转推算到 t_to 时刻。
    使用 Stonyhurst 经度纬度，考虑纬度相关的自转速率。
    """
    # ATime 已在模块级导入，直接使用，无 import 开销
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
#  重投影（修复2/11：接收预提取的 target_shape + aia_wcs_2d）
# ============================================================
def reproject_radio_to_aia(radio_data:   np.ndarray,
                            radio_header: fits.Header,
                            radio_wcs:    WCS,
                            target_shape: Tuple[int, int],   # 由调用方预提取
                            aia_wcs_2d:   WCS,               # 由调用方预提取
                            radio_time:   Optional[datetime],
                            aia_time:     Optional[datetime],
                            height_rsun:  float,
                            cfg:          Config) -> Optional[np.ndarray]:
    """
    将射电图像重投影到 AIA 裁剪图的 WCS 和形状上。
    可选：太阳自转修正、数据级平滑。
    """
    try:
        reprojected, footprint = reproject_interp(
            (radio_data, radio_wcs), aia_wcs_2d,
            shape_out=target_shape, order=cfg.reproject_order
        )
    except Exception as e:
        print(f"    [警告] WCS 重投影失败: {e}")
        return None

    reprojected[footprint == 0] = np.nan

    if (cfg.apply_solar_rotation_correction
            and radio_time and aia_time
            and abs((aia_time - radio_time).total_seconds()) > 1.0):
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
                # mode='constant', cval=nan：位移边界正确填 nan，
                # 不叠加原始 footprint（原 footprint 未随位移，会错误掩有效区）
                reprojected = nd_shift(
                    np.nan_to_num(reprojected, nan=0.0),
                    shift=[shift_y, shift_x], order=1,
                    mode='constant', cval=np.nan
                )
        except Exception:
            pass

    # 修复6：用缓存的 kernel，sigma 相同时不重建
    if cfg.radio_smooth_sigma > 0:
        reprojected = convolve(reprojected,
                               _make_gaussian_kernel(cfg.radio_smooth_sigma),
                               preserve_nan=True)
    return reprojected

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
                       color_cache: List):     # 修复7：从 main() 接收，不在此重建
    """
    单个 AIA 图像 + 其所有射电时间切片。
    AIA 底图、HMI、aia_wcs_2d 只准备一次，全部子帧复用后彻底释放。
    """
    check_memory_usage(limit=90.0)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")

    # 修复8：O(1) 字典，替代 list.index() O(n)
    selected_bands_idx: Dict[str, int] = {b: i for i, b in enumerate(cfg.selected_bands)}

    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else 'hot'

    # 修复3：初始化为 None，保证 finally del 始终安全
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

        # 修复2：提前提取一次，全部子帧/波段/fits 复用
        target_shape = cutout_aia.data.shape
        aia_wcs_2d   = cutout_aia.wcs
        if aia_wcs_2d.world_n_dim > 2:
            aia_wcs_2d = aia_wcs_2d.celestial
        target_wcs = cutout_aia.wcs   # 用于 ax 投影和 HMI

        # 预处理 HMI 磁图（若启用）
        hmi_processed = (process_hmi_for_overlay(hmi_file, target_wcs, cfg)
                         if cfg.overlay_hmi and hmi_file else None)

        # 修复9：makedirs 移出子帧循环，每组 AIA 最多执行一次
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)

        # 遍历该 AIA 对应的每个射电时间切片
        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=90.0)
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
            first_radio_time = None          # 修复10：单变量替代列表
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

            # 修复4：正则只搜索一次（命名函数，避免 lambda 中双搜索）
            def _band_freq_key(item: Tuple[str, list]) -> float:
                mobj = _RE_BAND_SORTED.search(item[0])
                return float(mobj.group(1)) if mobj else 0.0

            # 修复14：band_groups 在 build_matched_pairs 已按时间排好序，
            # 此处只需按频率对波段排序
            sorted_bands = sorted(single_slice_bands.items(), key=_band_freq_key)

            # --- 3. 叠加射电等值线（每个波段一种颜色）---
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_band_idx = selected_bands_idx.get(band_label, band_idx)  # 修复8
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
                        # 修复1：beam params 在 with 块内读取，FITS 关闭前完成
                        with fits.open(fits_path) as hdul:
                            img_hdu = next(
                                (h for h in hdul
                                 if isinstance(h, (fits.PrimaryHDU, fits.ImageHDU))
                                 and h.data is not None and h.data.ndim >= 2),
                                hdul[0]
                            )
                            radio_data_2d, radio_header_2d = extract_radio_2d_data(img_hdu)
                            beam = get_beam_params_from_header(img_hdu.header)  # ← with 内

                        if radio_data_2d is None or radio_data_2d.size == 0:
                            continue

                        radio_wcs_2d = build_radio_wcs_2d(
                            radio_header_2d, radio_time, cutout_aia.meta)

                        if beam and band_label not in collected_beams:
                            collected_beams[band_label] = beam

                        # 修复2/11：传 target_shape + aia_wcs_2d，不传整个 cutout_aia
                        reprojected = reproject_radio_to_aia(
                            radio_data_2d, radio_header_2d, radio_wcs_2d,
                            target_shape, aia_wcs_2d,
                            radio_time, aia_time, height_rsun, cfg
                        )
                        if (reprojected is None
                                or np.isnan(np.nanmax(reprojected))
                                or np.nanmax(reprojected) <= 0):
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

                        # 修复10：只记录第一个时间
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
        # 修复3：去除死代码，变量已初始化为 None，直接 del 始终安全
        del aia_map, cutout_aia, hmi_processed
        gc.collect()

# ============================================================
def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """
    扫描并匹配 AIA 图像与射电数据、HMI 磁图。
    返回任务列表，每个元素为 (aia_file, hmi_file, sub_tasks)，
    其中 sub_tasks 是该 AIA 对应的所有时间切片，每个切片是一个波段->单个观测的字典。
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
    radio_files = list(set(files_in_pol_dir + files_with_pol_name))
    print(f"成功锁定 {len(radio_files)} 个 {pol} 射电文件。正在提取观测时间...")

    radio_cache: List[Dict] = []
    for rf in radio_files:
        band_found = next((b for b in cfg.selected_bands if b in rf), None)
        if not band_found:
            continue
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
                radio_cache.append({'path': rf, 'band': band_found,
                                    'pol': pol, 'time': r_time})
        except Exception:
            pass

    start_idx        = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx          = cfg.aia_file_end_idx   if cfg.aia_file_end_idx   is not None else len(aia_files)
    target_aia_files = aia_files[start_idx:end_idx]

    hmi_threshold_sec = cfg.hmi_time_threshold * 3600   # 避免循环内重复乘法
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

        # 修复14：在匹配阶段排序 + 截断，process 时无需每帧重复 sorted()
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
def main():
    cfg = Config()

    # 修复7：颜色缓存整个运行只构建一次，传给每次 process_aia_group 调用
    color_cache = _build_band_color_cache(cfg)

    grouped_tasks = build_matched_pairs(cfg)
    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return

    for task_index, (aia_file, hmi_file, sub_tasks) in enumerate(grouped_tasks):
        process_aia_group(
            aia_file=aia_file,
            hmi_file=hmi_file,
            sub_tasks=sub_tasks,
            task_index=task_index + 1,
            total_tasks=len(grouped_tasks),
            cfg=cfg,
            color_cache=color_cache,
        )

if __name__ == "__main__":
    main()