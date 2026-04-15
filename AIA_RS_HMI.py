# -*- coding: utf-8 -*-
"""
AIA_RS_HMI.py - AIA, 射电和HMI数据叠加绘图脚本
功能：将射电等值线叠加到AIA 171Å图像上，可选叠加HMI磁图等值线
"""

# ============================================================
# 1. 基础库导入
# ============================================================
import gc
import glob
import os
import re
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache, partial
from typing import Dict, List, Optional, Tuple

# ============================================================
# 2. 科学计算和天文库导入
# ============================================================
import astropy.units as u
import matplotlib
matplotlib.use("Agg")  # 非交互后端，子进程安全，节省内存
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import psutil
import sunpy.coordinates
import sunpy.map
from astropy.convolution import Gaussian2DKernel, convolve
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse
from scipy.ndimage import gaussian_filter
from sunpy.coordinates import frames

warnings.filterwarnings("ignore")

# ============================================================
# 3. 全局配置和常量
# ============================================================

# 字体设置
plt.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 正则表达式常量
_RE_MHZ = re.compile(r"(\d+\.?\d*)\s*MHz", re.IGNORECASE)
_RE_AIA_PATS = [
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits"),
    re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{6}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"),
    re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{4}\d{2}\d{2}T\d{2}\d{2}\d{2})"),
]
_RE_HMI_PAT = re.compile(r"(\d{8})_(\d{6})")
_RE_BAND_SORTED = re.compile(r"(\d+\.?\d*)MHz")
_RE_RADIO_PAT_YYYYJJJ = re.compile(r"(\d{7})_(\d{6})_(\d{1,3})")
_RE_RADIO_PAT_YYYYMMDD = re.compile(r"(\d{8})_(\d{6})")
_RE_AIA_NEW_PAT = re.compile(r"aia\.lev1_euv_12s\.(\d{4}-\d{2}-\d{2}T\d{6}Z)\.\d+\.image_lev1\.fits")
_RE_HMI_NEW_PAT = re.compile(r"hmi\.M_45s\.(\d{8})_(\d{6})_TAI")

# 时间格式常量
_DATETIME_FMTS = [
    # 标准ISO格式
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H%M%S.%f",
    "%Y-%m-%dT%H%M%S",
    # 带时区信息
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H%M%S.%fZ",
    "%Y%m%dT%H%M%SZ",
    # 空格分隔
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H%M%S.%f",
    "%Y-%m-%d %H%M%S",
    # 简写格式
    "%Y%m%dT%H%M%S.%f",
    "%Y%m%dT%H%M%S",
    "%Y%m%d%H%M%S.%f",
    "%Y%m%d%H%M%S",
    # HMI格式
    "%Y%m%d_%H%M%S",
    # 其他常见格式
    "%d/%m/%YT%H:%M:%S.%f",
    "%d/%m/%YT%H:%M:%S",
    "%d-%b-%YT%H:%M:%S.%f",
    "%d-%b-%YT%H:%M:%S",
    # 射电文件特殊格式
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M%S.%f",
    "%Y%j%H%M%S.%f",
    "%Y%j%H%M%S",
]

# ============================================================
# 4. 配置类
# ============================================================
@dataclass
class Config:
    """主要配置参数类"""
    
    # 目录配置
    radio_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\RS_0447-0450"
    aia_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\171\1"
    hmi_base_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA\hmi\1"
    output_dir: str = r"D:\spike_topping_type_III\2025\20250124\AIA_RS_HMI\LL"
    
    # 文件处理配置
    save_figure: bool = True
    dpi: int = 300
    aia_file_start_idx: int = 392
    aia_file_end_idx: Optional[int] = 397
    
    # 射电波段配置
    selected_bands: List[str] = field(
        default_factory=lambda: [
            "149MHz", "164MHz", "190MHz", "223MHz", 
            "238MHz", "300MHz", "309MHz", "324MHz"
        ]
    )
    polarization_mode: str = "LL"
    radio_time_threshold: int = 6
    max_radio_per_band: int = 28
    
    # 等值线配置
    normalization_mode: str = "peak"
    contour_levels_peak: List[float] = field(default_factory=lambda: [0.95])
    rms_sigma_levels: List[float] = field(default_factory=lambda: [5.0, 15.0, 30.0])
    rms_box_fraction: float = 0.15
    contour_linewidths: List[float] = field(default_factory=lambda: [2.0])
    contour_alpha: float = 0.90
    contour_smooth_sigma: float = 0
    
    # 显示配置
    show_beam: bool = True
    beam_inset_fraction: float = 0.12
    overlay_hmi: bool = True
    hmi_time_threshold: int = 24
    hmi_threshold_gauss: float = 0.0
    hmi_sigma: int = 2
    hmi_levels_gauss: List[float] = field(default_factory=lambda: [100.0])
    
    # AIA图像配置
    aia_vmin: float = 16
    aia_vmax: float = 6666
    aia_cmap: str = "sdoaia171"
    roi_bottom_left: List[float] = field(default_factory=lambda: [-3000, -3000])
    roi_top_right: List[float] = field(default_factory=lambda: [3000, 3000])
    
    # 颜色配置
    band_colors_dict: dict = field(
        default_factory=lambda: {
            "149.0MHz": ("cyan", "deepskyblue"),
            "164.0MHz": ("lime", "green"),
            "190.0MHz": ("magenta", "darkviolet"),
            "205.0MHz": ("yellow", "orange"),
            "223.0MHz": ("red", "darkred"),
            "238.0MHz": ("white", "lightgray"),
        }
    )
    default_colors: List[Tuple] = field(
        default_factory=lambda: [
            ("yellow", "orange"),
            ("red", "darkred"),
            ("white", "lightgray"),
            ("pink", "hotpink"),
            ("skyblue", "deepskyblue"),
            ("violet", "darkviolet"),
        ]
    )
    
    # 性能配置
    num_workers: int = 8
    memory_limit_pct: float = 85.0
    radio_use_float32: bool = True
    
    # 处理选项
    apply_background_subtraction: bool = False
    debug_mode: bool = True
    
    # 坐标处理配置
    coordinate_search_radius: float = 3.0
    quick_test: bool = False
    test_file_limit: int = 5
    
    # 坐标图配置
    use_radec_maps: bool = True
    radio_to_solar_scale_factor: float = 0.05
    auto_adjust_scale_factor: bool = True
    min_pixels_in_view: int = 100
    max_scale_factor_adjustments: int = 3

# ============================================================
# 5. 工具函数 - 时间处理
# ============================================================
def _parse_flexible_datetime(date_str: str) -> Optional[datetime]:
    """灵活解析各种时间格式"""
    date_str = date_str.strip()
    
    # 处理17位数字格式（YYYYMMDDHHMMSSmmm）
    if len(date_str) == 17 and date_str.isdigit():
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[8:10])
            minute = int(date_str[10:12])
            second = int(date_str[12:14])
            millisecond = int(date_str[14:17])
            microsecond = millisecond * 1000
            return datetime(year, month, day, hour, minute, second, microsecond)
        except Exception:
            pass
    
    # 处理下划线分隔格式（YYYYJJJ_HHMMSS_SSS）
    if "_" in date_str:
        parts = date_str.split("_")
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1]
            
            if len(date_part) == 7:
                year = int(date_part[:4])
                parsed_date = None
                
                # 尝试解析为YYYYmDD格式
                try:
                    month_candidate = int(date_part[4:5])
                    day_candidate = int(date_part[5:7])
                    parsed_date = datetime(year, month_candidate, day_candidate)
                except ValueError:
                    pass
                
                # 回退到年+儒略日
                if parsed_date is None:
                    try:
                        doy = int(date_part[4:])
                        parsed_date = datetime(year, 1, 1) + timedelta(days=doy - 1)
                    except Exception:
                        pass
                
                if parsed_date is not None and len(time_part) == 6:
                    hour = int(time_part[0:2])
                    minute = int(time_part[2:4])
                    second = int(time_part[4:6])
                    microsecond = 0
                    
                    if len(parts) > 2 and parts[2]:
                        ms_str = parts[2].strip().ljust(3, "0")[:3]
                        microsecond = int(ms_str) * 1000
                    
                    return datetime(
                        parsed_date.year, parsed_date.month, parsed_date.day,
                        hour, minute, second, microsecond
                    )
    
    # 处理小数点格式
    if "." in date_str:
        integer_part, decimal_part = date_str.split(".")
        decimal_part = decimal_part.ljust(6, "0")[:6]
        date_str = f"{integer_part}.{decimal_part}"
    
    # 尝试标准格式
    for fmt in _DATETIME_FMTS:
        try:
            if ".%f" in fmt and "." not in date_str:
                date_str = date_str + ".0"
            if "." in date_str and ".%f" in fmt:
                integer_part, decimal_part = date_str.split(".")
                decimal_part = decimal_part.ljust(6, "0")[:6]
                date_str = f"{integer_part}.{decimal_part}"
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # 特殊处理14位数字格式
    if len(date_str) >= 14 and date_str[:14].isdigit():
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            hour = int(date_str[8:10])
            minute = int(date_str[10:12])
            second = int(date_str[12:14])
            microsecond = 0
            
            if len(date_str) > 14 and date_str[14] == ".":
                ms_str = date_str[15:].ljust(6, "0")[:6]
                microsecond = int(ms_str)
            elif len(date_str) > 14:
                remaining = date_str[14:]
                if remaining.isdigit():
                    if len(remaining) == 3:
                        millisecond = int(remaining)
                        microsecond = millisecond * 1000
                    else:
                        ms_str = remaining.ljust(6, "0")[:6]
                        microsecond = int(ms_str)
            
            return datetime(year, month, day, hour, minute, second, microsecond)
        except Exception:
            pass
    
    return None

def parse_radio_time_from_filename(filename: str) -> Optional[datetime]:
    """从射电文件名中提取观测时间"""
    basename = os.path.basename(filename)
    
    # 格式1: YYYYJJJ_HHMMSS_SSS
    m1 = _RE_RADIO_PAT_YYYYJJJ.search(basename)
    if m1:
        date_part = m1.group(1)
        time_part = m1.group(2)
        ms_part = m1.group(3)
        time_str = f"{date_part}_{time_part}_{ms_part}"
        parsed_time = _parse_flexible_datetime(time_str)
        if parsed_time:
            return parsed_time
    
    # 格式2: YYYYMMDD_HHMMSS
    m2 = _RE_RADIO_PAT_YYYYMMDD.search(basename)
    if m2:
        date_part = m2.group(1)
        time_part = m2.group(2)
        time_str = f"{date_part}_{time_part}"
        parsed_time = _parse_flexible_datetime(time_str)
        if parsed_time:
            return parsed_time
    
    # 从头文件读取
    try:
        if os.path.exists(filename):
            header = fits.getheader(filename, 0)
            date_obs = str(header.get("DATE-OBS", "")).strip()
            if date_obs:
                parsed_time = _parse_flexible_datetime(date_obs)
                if parsed_time:
                    return parsed_time
    except Exception:
        pass
    
    return None

def parse_aia_time_from_filename(filename: str) -> Optional[datetime]:
    """从AIA文件名中提取观测时间"""
    basename = os.path.basename(filename)
    
    # 尝试从头文件读取
    try:
        if os.path.exists(filename):
            header = fits.getheader(filename, 0)
            date_obs = str(header.get("DATE-OBS", "")).strip()
            if date_obs:
                parsed_time = _parse_flexible_datetime(date_obs)
                if parsed_time:
                    return parsed_time
    except Exception:
        pass
    
    # 尝试新格式
    m = _RE_AIA_NEW_PAT.search(basename)
    if m:
        ts = m.group(1).rstrip("Z")
        parsed_time = _parse_flexible_datetime(ts)
        if parsed_time:
            return parsed_time
    
    # 原有解析模式
    for pat in _RE_AIA_PATS:
        m = pat.search(basename)
        if m:
            ts = m.group(1).rstrip("Z")
            parsed_time = _parse_flexible_datetime(ts)
            if parsed_time:
                return parsed_time
    
    # 直接提取数字部分
    all_digits = re.findall(r"\d{4,}", basename)
    for digits in all_digits:
        if len(digits) >= 8:
            parsed_time = _parse_flexible_datetime(digits)
            if parsed_time:
                return parsed_time
    
    return None

def parse_hmi_time_from_filename(filename: str) -> Optional[datetime]:
    """从HMI文件名中提取观测时间"""
    basename = os.path.basename(filename)
    
    # 新格式
    m1 = _RE_HMI_NEW_PAT.search(basename)
    if m1:
        date_part = m1.group(1)
        time_part = m1.group(2)
        time_str = f"{date_part}_{time_part}"
        try:
            return datetime.strptime(time_str, "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    
    # 原有格式
    m2 = _RE_HMI_PAT.search(basename)
    if m2:
        try:
            return datetime.strptime(f"{m2.group(1)}_{m2.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    
    return None

def parse_radio_time_from_header(header: fits.Header) -> Optional[datetime]:
    """从FITS头中解析射电观测时间"""
    time_keys = [
        "DATE-OBS", "DATE_OBS", "DATEOBS",
        "DATE-BEG", "DATE_BEG", "DATEBEG",
        "TIME-OBS", "DATE",
    ]
    
    for key in time_keys:
        if key in header:
            date_str = str(header[key]).strip()
            if not date_str:
                continue
            
            # 处理多个空格
            if "  " in date_str:
                date_str = " ".join(date_str.split())
            
            # 处理空格分隔的数字
            if " " in date_str:
                parts = date_str.split(" ")
                if len(parts) == 2:
                    integer_part = parts[0]
                    decimal_part = parts[1].ljust(3, "0")[:3]
                    date_str = f"{integer_part}.{decimal_part}"
            
            date_str = date_str.rstrip("Z")
            parsed_time = _parse_flexible_datetime(date_str)
            if parsed_time:
                return parsed_time
    
    return None

# ============================================================
# 6. 工具函数 - 坐标处理
# ============================================================
def get_sun_center_and_radius(header):
    """从FITS头文件中获取太阳中心坐标和半径"""
    try:
        crpix1 = header.get("CRPIX1", 0)
        crpix2 = header.get("CRPIX2", 0)
        crval1 = header.get("CRVAL1", 0)
        crval2 = header.get("CRVAL2", 0)
        cdelt1 = header.get("CDELT1", 1)
        cdelt2 = header.get("CDELT2", 1)
        
        if "RSUN_OBS" in header:
            rsun_obs = header["RSUN_OBS"]
        elif "R_SUN" in header and "CDELT1" in header:
            rsun_obs = abs(header["R_SUN"] * header["CDELT1"])
        else:
            rsun_obs = 960.0
        
        return crpix1, crpix2, crval1, crval2, cdelt1, cdelt2, rsun_obs
    except Exception as e:
        print(f"获取太阳信息时出错: {e}")
        return 0, 0, 0, 0, 1, 1, 960.0

def calculate_image_extent(data_shape, crpix1, crpix2, crval1, crval2, cdelt1, cdelt2):
    """计算图像的完整范围（角秒）"""
    nx, ny = data_shape[1], data_shape[0]
    
    x_min = crval1 + (1 - crpix1) * cdelt1
    x_max = crval1 + (nx - crpix1) * cdelt1
    y_min = crval2 + (1 - crpix2) * cdelt2
    y_max = crval2 + (ny - crpix2) * cdelt2
    
    if cdelt1 > 0:
        x_extent = [x_min, x_max]
    else:
        x_extent = [x_max, x_min]
    
    if cdelt2 > 0:
        y_extent = [y_min, y_max]
    else:
        y_extent = [y_max, y_min]
    
    return x_extent, y_extent

def get_solar_position(obs_time: datetime) -> Tuple[float, float]:
    """计算观测时刻太阳中心在ICRS坐标系中的位置"""
    try:
        from astropy.coordinates import get_sun
        from astropy.time import Time
        
        astropy_time = Time(obs_time, format="datetime", scale="utc")
        sun_coord = get_sun(astropy_time)
        return sun_coord.ra.deg, sun_coord.dec.deg
    except Exception as e:
        print(f"    [警告] 使用astropy计算太阳位置失败: {e}")
        return 306.413395, -19.231661

def generate_solar_coordinates(shape: Tuple[int, int], header: fits.Header, cfg: Config) -> Tuple[np.ndarray, np.ndarray]:
    """生成射电数据对应的太阳坐标（Tx, Ty）"""
    ny, nx = shape
    y_indices, x_indices = np.indices((ny, nx))
    center_x = nx // 2
    center_y = ny // 2
    
    cdelt1 = header.get("CDELT1", 0.0)
    cdelt2 = header.get("CDELT2", 0.0)
    
    if cdelt1 == 0.0:
        if nx == 256 and ny == 256:
            cdelt1 = 0.0078
        else:
            cdelt1 = 0.0039
    
    if cdelt2 == 0.0:
        cdelt2 = cdelt1
    
    cdelt1_arcsec = cdelt1 * 3600.0 * cfg.radio_to_solar_scale_factor
    cdelt2_arcsec = cdelt2 * 3600.0 * cfg.radio_to_solar_scale_factor
    
    tx_map = (x_indices - center_x) * cdelt1_arcsec
    ty_map = (y_indices - center_y) * cdelt2_arcsec
    
    if cfg.debug_mode:
        print(f"    [太阳坐标] 生成坐标图: 形状={shape}")
        print(f"    [太阳坐标] 像素尺度: {cdelt1_arcsec:.4f}角秒/像素")
        print(f"    [太阳坐标] Tx范围: [{tx_map.min():.1f}, {tx_map.max():.1f}]角秒")
        print(f"    [太阳坐标] Ty范围: [{ty_map.min():.1f}, {ty_map.max():.1f}]角秒")
    
    return tx_map, ty_map

def _preprocess_radec_maps(ra_map: np.ndarray, dec_map: np.ndarray, radio_header: Optional[fits.Header], cfg: Config) -> Tuple[np.ndarray, np.ndarray, bool]:
    """统一坐标预处理，返回处理后的赤经赤纬（度）"""
    if cfg.use_radec_maps:
        if cfg.debug_mode:
            print(f"    [坐标预处理] 使用赤经赤纬坐标图模式")
        
        ra = ra_map.copy().astype(np.float64)
        dec = dec_map.copy().astype(np.float64)
        
        ra_fin = ra[np.isfinite(ra)]
        dec_fin = dec[np.isfinite(dec)]
        if len(ra_fin) == 0 or len(dec_fin) == 0:
            return ra, dec, False
        
        ra_min, ra_max = float(ra_fin.min()), float(ra_fin.max())
        dec_min, dec_max = float(dec_fin.min()), float(dec_fin.max())
        
        if cfg.debug_mode:
            print(f"    [坐标预处理] 赤经范围: [{ra_min:.6f}, {ra_max:.6f}] 度")
            print(f"    [坐标预处理] 赤纬范围: [{dec_min:.6f}, {dec_max:.6f}] 度")
        
        # 标准化赤经
        if ra_min < 0 or ra_max > 360:
            ra = np.mod(ra, 360.0)
        
        return ra, dec, False
    else:
        if cfg.debug_mode:
            print(f"    [坐标预处理] 使用太阳坐标模式")
            print(f"    [坐标预处理] Tx范围: [{ra_map.min():.1f}, {ra_map.max():.1f}]角秒")
            print(f"    [坐标预处理] Ty范围: [{dec_map.min():.1f}, {dec_map.max():.1f}]角秒")
        
        return ra_map, dec_map, True

# ============================================================
# 7. 工具函数 - 数据处理
# ============================================================
def extract_radio_2d_data(fits_path: str, use_float32: bool = True, cfg: Optional[Config] = None) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], fits.Header, Optional[WCS]]:
    """提取射电数据和坐标图"""
    try:
        with fits.open(fits_path) as hdu_data:
            data = hdu_data[0].data
            while data.ndim > 2:
                data = data[0]
            data = np.squeeze(data)
            header = hdu_data[0].header.copy()
            
            ra_map = None
            dec_map = None
            
            if cfg is not None and cfg.use_radec_maps:
                base_dir = os.path.dirname(fits_path)
                base_name = os.path.basename(fits_path)
                
                # 提取频率
                freq_match = re.search(r"(\d+)MHz", base_name, re.IGNORECASE)
                freq_value = None
                if freq_match:
                    freq_value = freq_match.group(1)
                else:
                    dir_name = os.path.basename(base_dir)
                    dir_freq_match = re.search(r"(\d+)MHz", dir_name, re.IGNORECASE)
                    if dir_freq_match:
                        freq_value = dir_freq_match.group(1)
                
                if freq_value:
                    # 搜索坐标图文件
                    ra_patterns = [
                        f"{freq_value}MHz_RightAscensionDegree.fits",
                        f"{freq_value}MHz_RA.fits",
                        f"*{freq_value}*RightAscension*.fits",
                        f"*{freq_value}*RA*.fits"
                    ]
                    
                    dec_patterns = [
                        f"{freq_value}MHz_DeclinationDegree.fits",
                        f"{freq_value}MHz_Dec.fits",
                        f"*{freq_value}*Declination*.fits",
                        f"*{freq_value}*Dec*.fits"
                    ]
                    
                    search_dirs = [base_dir, os.path.dirname(base_dir), os.path.join(os.path.dirname(base_dir), "..")]
                    
                    ra_file_found = False
                    dec_file_found = False
                    
                    for search_dir in search_dirs:
                        if not os.path.isdir(search_dir):
                            continue
                        
                        # 查找赤经文件
                        if not ra_file_found:
                            for pattern in ra_patterns:
                                matches = glob.glob(os.path.join(search_dir, pattern))
                                for match in matches:
                                    try:
                                        with fits.open(match) as hdu_ra:
                                            ra_map = hdu_ra[0].data
                                            while ra_map.ndim > 2:
                                                ra_map = ra_map[0]
                                            ra_map = np.squeeze(ra_map)
                                            if use_float32:
                                                ra_map = ra_map.astype(np.float32)
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 已加载RA文件: {os.path.basename(match)}")
                                        ra_file_found = True
                                        break
                                    except Exception as e:
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 加载RA文件失败 {os.path.basename(match)}: {e}")
                                if ra_file_found:
                                    break
                        
                        # 查找赤纬文件
                        if not dec_file_found:
                            for pattern in dec_patterns:
                                matches = glob.glob(os.path.join(search_dir, pattern))
                                for match in matches:
                                    try:
                                        with fits.open(match) as hdu_dec:
                                            dec_map = hdu_dec[0].data
                                            while dec_map.ndim > 2:
                                                dec_map = dec_map[0]
                                            dec_map = np.squeeze(dec_map)
                                            if use_float32:
                                                dec_map = dec_map.astype(np.float32)
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 已加载Dec文件: {os.path.basename(match)}")
                                        dec_file_found = True
                                        break
                                    except Exception as e:
                                        if cfg.debug_mode:
                                            print(f"    [坐标图] 加载Dec文件失败 {os.path.basename(match)}: {e}")
                                if dec_file_found:
                                    break
                        
                        if ra_file_found and dec_file_found:
                            break
                    
                    if cfg.debug_mode:
                        if ra_file_found and dec_file_found:
                            print(f"    [坐标图] 成功加载赤经赤纬坐标图")
                        else:
                            print(f"    [坐标图] 警告: 未找到完整的坐标图文件")
            
            dtype = np.float32 if use_float32 else np.float64
            return data.astype(dtype), ra_map, dec_map, header, None
            
    except Exception as e:
        print(f"读取FITS文件失败 {fits_path}: {e}")
        return None, None, None, None, None

def estimate_rms_noise(data: np.ndarray, box_fraction: float = 0.15) -> float:
    """通过图像四个角部区域估算背景噪声 RMS"""
    ny, nx = data.shape
    bx = max(int(nx * box_fraction), 5)
    by = max(int(ny * box_fraction), 5)
    
    corners = [data[:by, :bx], data[:by, -bx:], data[-by:, :bx], data[-by:, -bx:]]
    corner_pixels = np.concatenate([c.ravel() for c in corners])
    corner_pixels = corner_pixels[~np.isnan(corner_pixels)]
    
    if len(corner_pixels) < 10:
        edges = np.concatenate([
            data[:by, :].ravel(),
            data[-by:, :].ravel(),
            data[:, :bx].ravel(),
            data[:, -bx:].ravel(),
        ])
        edge_pixels = edges[~np.isnan(edges)]
        if len(edge_pixels) > 0:
            corner_pixels = edge_pixels
    
    if len(corner_pixels) == 0:
        return float(np.nanstd(data) * 0.1)
    
    median = np.median(corner_pixels)
    mad = np.median(np.abs(corner_pixels - median))
    std_est = mad * 1.4826
    
    filtered = corner_pixels[np.abs(corner_pixels - median) < 3 * std_est]
    
    if len(filtered) > 0:
        return float(np.std(filtered))
    else:
        return float(std_est)

def compute_contour_levels(data: np.ndarray, cfg: Config) -> List[float]:
    """计算等值线级别"""
    finite_data = data[np.isfinite(data)]
    if len(finite_data) == 0:
        return []
    
    if cfg.normalization_mode == "rms":
        rms = estimate_rms_noise(data, cfg.rms_box_fraction)
        if rms <= 0:
            return []
        peak = float(np.nanmax(finite_data))
        levels = [s * rms for s in cfg.rms_sigma_levels if 0 < s * rms < peak]
    else:
        peak = float(np.nanmax(finite_data))
        levels = [f * peak for f in cfg.contour_levels_peak]
    
    return levels if levels else []

# ============================================================
# 8. 工具函数 - 重投影
# ============================================================
def reproject_radio_simple_scale(radio_data: np.ndarray, radio_header: fits.Header, aia_cutout_map, cfg: Config) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """简化的射电数据投影方法"""
    try:
        # 获取太阳信息
        (radio_crpix1, radio_crpix2, radio_crval1, radio_crval2, 
         radio_cdelt1, radio_cdelt2, radio_rsun) = get_sun_center_and_radius(radio_header)
        
        aia_header = aia_cutout_map.meta
        (aia_crpix1, aia_crpix2, aia_crval1, aia_crval2,
         aia_cdelt1, aia_cdelt2, aia_rsun) = get_sun_center_and_radius(aia_header)
        
        if cfg.debug_mode:
            print(f"    [简单投影] AIA太阳半径: {aia_rsun:.1f} arcsec")
            print(f"    [简单投影] 射电太阳半径: {radio_rsun:.1f} arcsec")
        
        # 计算缩放因子
        scale_factor = aia_rsun / radio_rsun
        
        # 计算射电图像范围
        radio_x_extent, radio_y_extent = calculate_image_extent(
            radio_data.shape,
            radio_crpix1, radio_crpix2,
            radio_crval1, radio_crval2,
            radio_cdelt1, radio_cdelt2,
        )
        
        radio_center_x = radio_crval1
        radio_center_y = radio_crval2
        
        scaled_radio_x_min = radio_center_x + (radio_x_extent[0] - radio_center_x) * scale_factor
        scaled_radio_x_max = radio_center_x + (radio_x_extent[1] - radio_center_x) * scale_factor
        scaled_radio_y_min = radio_center_y + (radio_y_extent[0] - radio_center_y) * scale_factor
        scaled_radio_y_max = radio_center_y + (radio_y_extent[1] - radio_center_y) * scale_factor
        
        scaled_radio_extent = [
            min(scaled_radio_x_min, scaled_radio_x_max),
            max(scaled_radio_x_min, scaled_radio_x_max),
            min(scaled_radio_y_min, scaled_radio_y_max),
            max(scaled_radio_y_min, scaled_radio_y_max),
        ]
        
        # 创建射电坐标网格
        ny, nx = radio_data.shape
        y_indices, x_indices = np.indices((ny, nx))
        
        tx_map = scaled_radio_extent[0] + (x_indices / (nx - 1)) * (scaled_radio_extent[1] - scaled_radio_extent[0])
        ty_map = scaled_radio_extent[2] + (y_indices / (ny - 1)) * (scaled_radio_extent[3] - scaled_radio_extent[2])
        
        # 获取AIA图像范围
        aia_x_extent, aia_y_extent = calculate_image_extent(
            aia_cutout_map.data.shape,
            aia_crpix1, aia_crpix2,
            aia_crval1, aia_crval2,
            aia_cdelt1, aia_cdelt2,
        )
        
        aia_extent = [
            min(aia_x_extent[0], aia_x_extent[1]),
            max(aia_x_extent[0], aia_x_extent[1]),
            min(aia_y_extent[0], aia_y_extent[1]),
            max(aia_y_extent[0], aia_y_extent[1]),
        ]
        
        # 重采样到AIA网格
        from scipy.interpolate import RegularGridInterpolator
        
        x_radio = np.linspace(scaled_radio_extent[0], scaled_radio_extent[1], nx)
        y_radio = np.linspace(scaled_radio_extent[2], scaled_radio_extent[3], ny)
        radio_data_clean = np.nan_to_num(radio_data, nan=0.0)
        
        interpolator = RegularGridInterpolator(
            (y_radio, x_radio),
            radio_data_clean,
            method='linear',
            bounds_error=False,
            fill_value=0.0
        )
        
        ny_aia, nx_aia = aia_cutout_map.data.shape
        x_aia = np.linspace(aia_extent[0], aia_extent[1], nx_aia)
        y_aia = np.linspace(aia_extent[2], aia_extent[3], ny_aia)
        X_aia, Y_aia = np.meshgrid(x_aia, y_aia)
        
        points = np.column_stack([Y_aia.ravel(), X_aia.ravel()])
        reprojected = interpolator(points).reshape(ny_aia, nx_aia)
        tx_aia = X_aia
        ty_aia = Y_aia
        
        if cfg.debug_mode:
            valid_count = np.sum(~np.isnan(reprojected))
            print(f"    [简单投影] 成功重投影: 有效像素 {valid_count}/{ny_aia*nx_aia}")
        
        return reprojected, tx_aia, ty_aia
        
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [简单投影] 异常: {e}")
        return None

def reproject_radio_forward_paste(radio_data: np.ndarray, ra_map: np.ndarray, dec_map: np.ndarray, aia_cutout_map, cfg: Config, radio_header: Optional[fits.Header] = None) -> Optional[np.ndarray]:
    """前向投影贴图法"""
    try:
        if ra_map is None or dec_map is None:
            if cfg.debug_mode:
                print("    [前向投影] 失败：坐标图为 None")
            return None
        
        if ra_map.shape != radio_data.shape or dec_map.shape != radio_data.shape:
            if cfg.debug_mode:
                print(f"    [前向投影] 失败：坐标图形状不匹配")
            return None
        
        # 预处理坐标图
        ra_abs, dec_abs, is_relative = _preprocess_radec_maps(ra_map, dec_map, radio_header, cfg)
        
        # 坐标转换
        if cfg.use_radec_maps:
            if cfg.debug_mode:
                print(f"    [坐标转换] 使用赤经赤纬坐标图，转换为太阳坐标")
            
            # 获取观测时间
            radio_time = None
            if radio_header is not None:
                time_keys = ["DATE-OBS", "DATE_OBS", "DATEOBS", "DATE-BEG", "DATE_BEG", "DATEBEG"]
                for key in time_keys:
                    if key in radio_header:
                        date_str = str(radio_header[key]).strip()
                        if date_str:
                            if "  " in date_str:
                                date_str = " ".join(date_str.split())
                            radio_time = _parse_flexible_datetime(date_str)
                            if radio_time:
                                break
            
            if radio_time is None:
                try:
                    radio_time = aia_cutout_map.date.to_datetime()
                except Exception:
                    from datetime import datetime
                    radio_time = datetime.now()
            
            # 转换为太阳坐标
            try:
                from astropy.coordinates import get_sun
                from astropy.time import Time
                
                astropy_time = Time(radio_time, format="datetime", scale="utc")
                radio_coords = SkyCoord(
                    ra=ra_abs * u.deg,
                    dec=dec_abs * u.deg,
                    frame='icrs',
                    obstime=astropy_time
                )
                
                with sunpy.coordinates.propagate_with_solar_surface():
                    radio_hpc = radio_coords.transform_to(aia_cutout_map.coordinate_frame)
            except Exception as e:
                if cfg.debug_mode:
                    print(f"    [警告] 坐标转换失败: {e}")
                return None
        else:
            # 太阳坐标模式
            try:
                radio_hpc = SkyCoord(
                    Tx=ra_abs * u.arcsec,
                    Ty=dec_abs * u.arcsec,
                    frame=aia_cutout_map.coordinate_frame,
                )
            except Exception as e:
                if cfg.debug_mode:
                    print(f"    [太阳坐标模式] 构建太阳坐标失败: {e}")
                return None
        
        # 有效点筛选
        if cfg.use_radec_maps:
            valid_mask = np.isfinite(ra_abs) & np.isfinite(dec_abs) & np.isfinite(radio_data)
        else:
            valid_mask = np.isfinite(ra_abs) & np.isfinite(dec_abs) & np.isfinite(radio_data)
        
        n_valid = int(np.sum(valid_mask))
        if n_valid < 9:
            if cfg.debug_mode:
                print(f"    [前向投影] 失败：有效点不足 ({n_valid})")
            return None
        
        v_data = radio_data[valid_mask].astype(np.float64)
        
        # 获取像素坐标
        if hasattr(radio_hpc, '__len__') and len(radio_hpc) > 1:
            radio_hpc_valid = radio_hpc[valid_mask]
        else:
            radio_hpc_valid = radio_hpc
        
        px_f, py_f = aia_cutout_map.wcs.world_to_pixel(radio_hpc_valid)
        px_f = np.asarray(px_f, dtype=np.float64)
        py_f = np.asarray(py_f, dtype=np.float64)
        
        if np.isscalar(px_f):
            px_f = np.array([px_f])
            py_f = np.array([py_f])
        
        # 像素坐标有效性
        fin_pix = np.isfinite(px_f) & np.isfinite(py_f)
        px_i = np.round(px_f[fin_pix]).astype(int)
        py_i = np.round(py_f[fin_pix]).astype(int)
        v_vals = v_data[fin_pix]
        
        ny_aia, nx_aia = aia_cutout_map.data.shape
        in_bounds = (px_i >= 0) & (px_i < nx_aia) & (py_i >= 0) & (py_i < ny_aia)
        
        n_in = int(np.sum(in_bounds))
        if n_in == 0:
            return None
        
        # 散射到输出数组
        acc = np.full((ny_aia, nx_aia), -np.inf, dtype=np.float64)
        np.maximum.at(acc, (py_i[in_bounds], px_i[in_bounds]), v_vals[in_bounds])
        output = np.where(acc > -np.inf, acc, np.nan).astype(np.float32)
        
        # 间隙填充
        nan_mask = np.isnan(output)
        if nan_mask.any():
            fill_sigma = 15.0
            filled = np.where(nan_mask, 0.0, output)
            weights = (~nan_mask).astype(np.float64)
            sm_d = gaussian_filter(filled.astype(np.float64), sigma=fill_sigma)
            sm_w = gaussian_filter(weights, sigma=fill_sigma)
            with np.errstate(invalid="ignore", divide="ignore"):
                diffused = np.where(sm_w > 1e-6, sm_d / sm_w, np.nan)
            output = np.where(nan_mask, diffused.astype(np.float32), output)
        
        return output
        
    except Exception as e:
        if cfg.debug_mode:
            print(f"    [前向投影] 异常: {e}")
        return None

def reproject_radio_to_aia(radio_data: np.ndarray, radio_header: fits.Header, ra_map: Optional[np.ndarray], dec_map: Optional[np.ndarray], aia_cutout_map, cfg: Config) -> Optional[np.ndarray]:
    """重投影入口函数"""
    if ra_map is None or dec_map is None:
        if cfg.debug_mode:
            print("    reproject_radio_to_aia: 无坐标图，跳过")
        return None
    
    return reproject_radio_forward_paste(
        radio_data, ra_map, dec_map, aia_cutout_map, cfg, radio_header=radio_header
    )

# ============================================================
# 9. 工具函数 - 绘图辅助
# ============================================================
def smooth_for_contour(data: np.ndarray, sigma: float) -> np.ndarray:
    """等值线平滑"""
    if sigma <= 0:
        return data
    nan_mask = np.isnan(data)
    filled = np.where(nan_mask, 0.0, data)
    weights = (~nan_mask).astype(np.float64)
    smooth_d = gaussian_filter(filled, sigma=sigma)
    smooth_w = gaussian_filter(weights, sigma=sigma)
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(smooth_w > 1e-6, smooth_d / smooth_w, np.nan)
    return result

def get_beam_params_from_header(header: fits.Header) -> Optional[Dict]:
    """从FITS头提取波束椭圆参数"""
    bmaj = header.get("BMAJ", None)
    bmin = header.get("BMIN", None)
    bpa = header.get("BPA", 0.0)
    if bmaj is None or bmin is None:
        return None
    return {
        "bmaj_arcsec": float(bmaj) * 3600.0,
        "bmin_arcsec": float(bmin) * 3600.0,
        "bpa_deg": float(bpa),
    }

def draw_beam_ellipse_pixel(ax, beam: Dict, aia_cutout_map: sunpy.map.GenericMap, color: str = "white"):
    """在图像左下角绘制波束椭圆"""
    cdelt = abs(aia_cutout_map.scale.axis1.to(u.arcsec / u.pix).value)
    bmaj_px = beam["bmaj_arcsec"] / cdelt
    bmin_px = beam["bmin_arcsec"] / cdelt
    ny, nx = aia_cutout_map.data.shape
    cx_px, cy_px = nx * 0.08, ny * 0.08
    
    ellipse = Ellipse(
        xy=(cx_px, cy_px),
        width=bmin_px,
        height=bmaj_px,
        angle=beam["bpa_deg"],
        linewidth=1.5,
        edgecolor=color,
        facecolor="none",
        alpha=0.85,
    )
    ax.add_patch(ellipse)
    
    ax.text(
        cx_px,
        cy_px - bmaj_px * 0.7,
        "Beam",
        color=color,
        fontsize=8,
        ha="center",
        va="top",
        alpha=0.85,
    )

def _build_band_color_cache(cfg: Config) -> List[Tuple[float, Tuple]]:
    """构建波段颜色缓存"""
    cache = []
    for key, val in cfg.band_colors_dict.items():
        m = _RE_MHZ.search(key)
        if m:
            cache.append((float(m.group(1)), val))
    return cache

def get_band_color(band_label: str, band_idx: int, cfg: Config, color_cache: Optional[List] = None) -> Tuple[str, str]:
    """根据波段标签返回颜色"""
    m = _RE_MHZ.search(band_label)
    if m and color_cache is not None:
        label_mhz = float(m.group(1))
        for key_mhz, val in color_cache:
            if abs(key_mhz - label_mhz) < 0.5:
                return val
    return cfg.default_colors[band_idx % len(cfg.default_colors)]

def process_hmi_for_overlay(hmi_file: str, target_wcs, cfg: Config) -> Optional[sunpy.map.GenericMap]:
    """处理HMI磁图用于叠加"""
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
# 10. 工具函数 - 系统辅助
# ============================================================
def check_memory_usage(limit: float = 90.0):
    """检查内存占用"""
    mem_percent = psutil.virtual_memory().percent
    if mem_percent >= limit:
        print(f"\n[警告] 内存占用已达 {mem_percent}% (阈值: {limit}%)，正在清理...")
        while psutil.virtual_memory().percent >= limit:
            gc.collect()
            time.sleep(1.0)
        print(f"[恢复] 内存占用已降至 {psutil.virtual_memory().percent}%")

@lru_cache(maxsize=16)
def _make_gaussian_kernel(sigma: float) -> Gaussian2DKernel:
    """Gaussian核缓存"""
    return Gaussian2DKernel(x_stddev=sigma)

def _worker_init():
    """子进程初始化"""
    import matplotlib
    matplotlib.use("Agg")
    import warnings
    warnings.filterwarnings("ignore")

# ============================================================
# 11. 核心处理函数
# ============================================================
def _read_one_radio_header(rf: str, selected_bands: Tuple[str, ...], pol: str, cfg: Config) -> Optional[Dict]:
    """读取单个射电文件头信息"""
    band_found = next((b for b in selected_bands if b in rf), None)
    if not band_found:
        return None
    
    try:
        # 优先从文件名解析时间
        r_time = parse_radio_time_from_filename(rf)
        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}
        
        # 从头文件读取
        hdr = fits.getheader(rf)
        r_time = parse_radio_time_from_header(hdr)
        
        if r_time:
            return {"path": rf, "band": band_found, "pol": pol, "time": r_time}
        elif cfg.debug_mode:
            print(f"    警告: 无法解析射电文件时间: {os.path.basename(rf)}")
            
    except Exception as e:
        if cfg.debug_mode:
            print(f"    读取射电文件头出错: {os.path.basename(rf)}, 错误: {str(e)[:100]}")
    
    return None

def build_matched_pairs(cfg: Config) -> List[Tuple[str, Optional[str], List]]:
    """构建匹配的数据对"""
    print("=" * 60)
    print("正在扫描并进行横向切片匹配，请稍候...")
    
    # 获取文件列表
    aia_files = sorted(glob.glob(os.path.join(cfg.aia_base_dir, "*.fits")))
    hmi_files = sorted(glob.glob(os.path.join(cfg.hmi_base_dir, "*.fits")))
    
    if not aia_files:
        print("[错误] 找不到 AIA 文件，请检查 cfg.aia_base_dir")
        return []
    
    # 快速测试模式
    if cfg.quick_test:
        print("[快速测试模式] 只处理前几个文件")
        aia_files = aia_files[: min(5, len(aia_files))]
    
    # 解析HMI时间
    hmi_times = []
    for hf in hmi_files:
        t = parse_hmi_time_from_filename(os.path.basename(hf))
        if t:
            hmi_times.append((hf, t))
    
    # 获取射电文件
    pol = cfg.polarization_mode
    files_in_pol_dir = glob.glob(os.path.join(cfg.radio_base_dir, "**", pol, "*.fits"), recursive=True)
    files_with_pol_name = glob.glob(os.path.join(cfg.radio_base_dir, "**", f"*{pol}*.fits"), recursive=True)
    
    # 过滤坐标图文件
    radio_files = []
    for f in list(set(files_in_pol_dir + files_with_pol_name)):
        if "_RightAscensionDegree.fits" in f or "_DeclinationDegree.fits" in f:
            continue
        radio_files.append(f)
    
    if cfg.quick_test:
        radio_files = radio_files[: min(10, len(radio_files))]
    
    print(f"成功锁定 {len(radio_files)} 个 {pol} 射电数据文件。正在并发提取观测时间...")
    
    # 并发读取头文件
    max_io_threads = min(32, (os.cpu_count() or 4) * 2, max(1, len(radio_files)))
    selected_bands_tuple = tuple(cfg.selected_bands)
    _read_fn = partial(_read_one_radio_header, selected_bands=selected_bands_tuple, pol=pol, cfg=cfg)
    
    radio_cache: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_io_threads) as executor:
        results = executor.map(_read_fn, radio_files)
        radio_cache = [r for r in results if r is not None]
    
    print(f"  读取完毕，有效射电观测记录: {len(radio_cache)} 条")
    
    # 文件范围选择
    start_idx = cfg.aia_file_start_idx if cfg.aia_file_start_idx is not None else 0
    end_idx = cfg.aia_file_end_idx if cfg.aia_file_end_idx is not None else len(aia_files)
    target_aia_files = aia_files[start_idx:end_idx]
    
    hmi_threshold_sec = cfg.hmi_time_threshold * 3600
    grouped_tasks = []
    match_stats = {"aia_processed": 0, "aia_matched": 0, "total_slices": 0}
    
    for aia_file in target_aia_files:
        match_stats["aia_processed"] += 1
        aia_time = parse_aia_time_from_filename(os.path.basename(aia_file))
        if not aia_time:
            print(f"  警告: 无法解析AIA文件时间: {os.path.basename(aia_file)}")
            continue
        
        # 寻找最接近的HMI文件
        best_hmi = None
        if hmi_times:
            valid_hmis = [hf for hf in hmi_times if abs((hf[1] - aia_time).total_seconds()) <= hmi_threshold_sec]
            if valid_hmis:
                best_hmi = min(valid_hmis, key=lambda x: abs((x[1] - aia_time).total_seconds()))[0]
        
        # 收集时间阈值内的射电数据
        band_groups: Dict[str, list] = {}
        for rc in radio_cache:
            time_diff = abs((rc["time"] - aia_time).total_seconds())
            if time_diff <= cfg.radio_time_threshold:
                band_groups.setdefault(rc["band"], []).append(
                    (rc["path"], rc["pol"], rc["time"], time_diff)
                )
        
        if not band_groups:
            if cfg.debug_mode:
                print(f"  AIA时间 {aia_time}: 无射电数据匹配")
            continue
        
        match_stats["aia_matched"] += 1
        
        # 每个波段排序截断
        for band in band_groups:
            band_groups[band].sort(key=lambda x: x[3])
            band_groups[band] = band_groups[band][: cfg.max_radio_per_band]
        
        # 确定横向切片数量
        min_count = min(len(v) for v in band_groups.values())
        if min_count == 0:
            continue
        
        # 构建横向切片
        tasks_for_this_aia = []
        for sub_index in range(min_count):
            slice_bands = {}
            for band in band_groups:
                if sub_index < len(band_groups[band]):
                    slice_bands[band] = [band_groups[band][sub_index][:3]]
            
            if slice_bands:
                tasks_for_this_aia.append((sub_index, slice_bands))
                match_stats["total_slices"] += 1
        
        if tasks_for_this_aia:
            grouped_tasks.append((aia_file, best_hmi, tasks_for_this_aia))
    
    # 打印统计信息
    print(f"\n匹配结果统计:")
    print(f"  处理的AIA文件: {match_stats['aia_processed']}")
    print(f"  成功匹配的AIA文件: {match_stats['aia_matched']}")
    print(f"  创建的切片总数: {match_stats['total_slices']}")
    print(f"  成功创建了 {len(grouped_tasks)} 组以 AIA 为核心的任务。")
    print("=" * 60)
    return grouped_tasks

def process_aia_group(aia_file: str, hmi_file: Optional[str], sub_tasks: List[Tuple[int, Dict]], task_index: int, total_tasks: int, cfg: Config, color_cache: List):
    """处理单个AIA文件组"""
    check_memory_usage(limit=cfg.memory_limit_pct)
    print(f"\n[{task_index}/{total_tasks}] 加载 AIA: {os.path.basename(aia_file)}")
    
    selected_bands_idx: Dict[str, int] = {b: i for i, b in enumerate(cfg.selected_bands)}
    aia_cmap_name = cfg.aia_cmap if cfg.aia_cmap in plt.colormaps() else "hot"
    
    aia_map = cutout_aia = hmi_processed = None
    
    try:
        # 加载AIA地图
        aia_map = sunpy.map.Map(aia_file)
        
        # 裁剪ROI
        bl = SkyCoord(
            Tx=cfg.roi_bottom_left[0] * u.arcsec,
            Ty=cfg.roi_bottom_left[1] * u.arcsec,
            frame=aia_map.coordinate_frame,
        )
        tr = SkyCoord(
            Tx=cfg.roi_top_right[0] * u.arcsec,
            Ty=cfg.roi_top_right[1] * u.arcsec,
            frame=aia_map.coordinate_frame,
        )
        cutout_aia = aia_map.submap(bl, top_right=tr)
        
        # 处理HMI
        hmi_processed = process_hmi_for_overlay(hmi_file, cutout_aia.wcs, cfg) if cfg.overlay_hmi and hmi_file else None
        
        # 创建输出目录
        if cfg.save_figure:
            os.makedirs(cfg.output_dir, exist_ok=True)
        
        # 处理每个切片
        for sub_index, single_slice_bands in sub_tasks:
            check_memory_usage(limit=cfg.memory_limit_pct)
            print(f"  -> 绘制序列帧 {sub_index + 1}/{len(sub_tasks)}")
            
            # 创建图形
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111, projection=cutout_aia.wcs)
            
            # 绘制AIA底图
            cutout_aia.plot(
                axes=ax,
                norm=mcolors.LogNorm(vmin=cfg.aia_vmin, vmax=cfg.aia_vmax),
                cmap=aia_cmap_name,
                title=False,
            )
            ax.coords.grid(False)
            
            legend_handles = []
            first_radio_time = None
            collected_beams: Dict[str, Dict] = {}
            
            # 叠加HMI等值线
            if hmi_processed is not None:
                ax.contour(
                    hmi_processed.data,
                    levels=cfg.hmi_levels_gauss,
                    colors=["red"],
                    linewidths=0.8,
                    alpha=0.7,
                )
                ax.contour(
                    hmi_processed.data,
                    levels=[-lv for lv in cfg.hmi_levels_gauss],
                    colors=["blue"],
                    linewidths=0.8,
                    alpha=0.7,
                )
                legend_handles += [
                    Line2D([0], [0], color="red", lw=0.8, label=f"+{cfg.hmi_levels_gauss[0]:.0f}G"),
                    Line2D([0], [0], color="blue", lw=0.8, label=f"-{cfg.hmi_levels_gauss[0]:.0f}G"),
                ]
            
            # 按频率排序波段
            sorted_bands = sorted(
                single_slice_bands.items(),
                key=lambda x: (
                    float(_RE_BAND_SORTED.search(x[0]).group(1))
                    if _RE_BAND_SORTED.search(x[0])
                    else 0.0
                ),
            )
            
            # 叠加射电等值线
            for band_idx, (band_label, file_list) in enumerate(sorted_bands):
                orig_band_idx = selected_bands_idx.get(band_label, band_idx)
                main_color, dark_color = get_band_color(band_label, orig_band_idx, cfg, color_cache)
                
                drawn_any = False
                for fits_path, polarization, radio_time in file_list:
                    if cfg.polarization_mode != "BOTH" and polarization != cfg.polarization_mode:
                        continue
                    
                    try:
                        # 提取射电数据
                        radio_data_2d, ra_map, dec_map, radio_header_2d, _ = extract_radio_2d_data(
                            fits_path, use_float32=cfg.radio_use_float32, cfg=cfg
                        )
                        
                        if radio_data_2d is None or radio_data_2d.size == 0:
                            continue
                        
                        # 获取波束信息
                        beam = get_beam_params_from_header(radio_header_2d)
                        if beam and band_label not in collected_beams:
                            collected_beams[band_label] = beam
                        
                        # 重投影
                        result = reproject_radio_simple_scale(
                            radio_data_2d,
                            radio_header_2d,
                            cutout_aia,
                            cfg,
                        )
                        
                        if result is None:
                            continue
                        
                        reprojected, tx_map, ty_map = result
                        
                        if np.isnan(np.nanmax(reprojected)) or np.nanmax(reprojected) <= 0:
                            continue
                        
                        # 计算等值线
                        display_data = smooth_for_contour(reprojected, cfg.contour_smooth_sigma)
                        levels = compute_contour_levels(display_data, cfg)
                        if not levels:
                            continue
                        
                        # 绘制等值线
                        n_lev = len(levels)
                        lws = [cfg.contour_linewidths[min(i, len(cfg.contour_linewidths) - 1)] for i in range(n_lev)]
                        colors_list = [dark_color if i < n_lev - 1 else main_color for i in range(n_lev)]
                        
                        ax.contour(
                            display_data,
                            levels=levels,
                            colors=colors_list,
                            linewidths=lws,
                            alpha=cfg.contour_alpha,
                        )
                        
                        if radio_time and first_radio_time is None:
                            first_radio_time = radio_time
                        drawn_any = True
                        
                    except Exception:
                        pass
                
                if drawn_any:
                    legend_handles.append(
                        Line2D([0], [0], color=main_color, linewidth=2.0, label=f"{band_label}")
                    )
            
            # 绘制波束椭圆
            if cfg.show_beam and collected_beams:
                for b_idx, (b_label, beam) in enumerate(collected_beams.items()):
                    b_color, _ = get_band_color(b_label, b_idx, cfg, color_cache)
                    draw_beam_ellipse_pixel(ax, beam, cutout_aia, color=b_color)
            
            # 绘制日面边缘
            cutout_aia.draw_limb(
                axes=ax,
                color="gray",
                linewidth=1.0,
                linestyle="--",
                alpha=0.6,
                label="Solar limb",
            )
            
            # 设置标题和图例
            title_time = first_radio_time.strftime("%Y-%m-%d %H:%M:%S") + " UT" if first_radio_time else os.path.basename(aia_file)
            ax.set_title(f"AIA 171Å + Radio ({cfg.polarization_mode}) + HMI\n{title_time}", fontsize=12, pad=10, color="white")
            ax.legend(
                handles=legend_handles,
                loc="upper right",
                fontsize=9,
                framealpha=0.6,
                facecolor="black",
                labelcolor="white",
            )
            
            # 样式调整
            fig.patch.set_facecolor("black")
            ax.set_facecolor("black")
            ax.tick_params(colors="white", direction="in")
            for spine in ax.spines.values():
                spine.set_edgecolor("white")
            ax.coords[0].set_axislabel("Solar X (arcsec)", color="white")
            ax.coords[1].set_axislabel("Solar Y (arcsec)", color="white")
            
            # 保存图像
            if cfg.save_figure:
                radio_time_str = first_radio_time.strftime("%Y%m%d_%H%M%S") if first_radio_time else f"unknown_{sub_index}"
                output_filename = f"{radio_time_str}_{cfg.polarization_mode}_seq{sub_index + 1:02d}.png"
                plt.savefig(
                    os.path.join(cfg.output_dir, output_filename),
                    dpi=cfg.dpi,
                    bbox_inches="tight",
                    facecolor="black",
                )
            
            # 清理
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
# 12. 主函数
# ============================================================
def test_time_parsing():
    """测试时间解析"""
    test_cases = [
        "20250124045940760",
        "20250124044317 38",
        "2025124_044317_038",
        "2025-01-24T04:43:17.038Z",
    ]
    
    print("测试时间解析:")
    for test_str in test_cases:
        result = _parse_flexible_datetime(test_str)
        if result:
            print(f"  '{test_str}' -> {result}")
        else:
            print(f"  '{test_str}' -> 解析失败")

def main():
    """主函数"""
    cfg = Config()
    
    # 测试时间解析
    if cfg.debug_mode:
        test_time_parsing()
        
        # 测试太阳位置计算
        print("\n测试太阳位置计算:")
        test_time = datetime(2025, 1, 24, 4, 43, 17)
        try:
            sun_ra, sun_dec = get_solar_position(test_time)
            print(f"  测试时间: {test_time}")
            print(f"  太阳位置: RA={sun_ra:.6f}°, Dec={sun_dec:.6f}°")
        except Exception as e:
            print(f"  太阳位置计算失败: {e}")
    
    # 颜色缓存
    color_cache = _build_band_color_cache(cfg)
    
    # 构建匹配对
    grouped_tasks = build_matched_pairs(cfg)
    if not grouped_tasks:
        print("[提示] 没有找到匹配的数据对。请检查时间阈值或路径设置。")
        return
    
    total = len(grouped_tasks)
    print(f"[模式] 单进程，共 {total} 组任务")
    
    # 处理每组任务
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
